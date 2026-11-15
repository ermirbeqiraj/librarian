"""Every request proves its caller before MCP sees it. On the homeserver Cloudflare Access
logs the caller in and signs a JWT into `Cf-Access-Jwt-Assertion`; on a dev machine, with
no Access, a bearer token from the environment. LIBRARIAN_AUTH picks one; there is no default.
"""

import asyncio
import hmac
import sys
from collections.abc import Awaitable, Callable

import jwt
from jwt import PyJWKClient
from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from librarian.hosts.config import ACCESS_AUD, ACCESS_TEAM, AUTH, BEARER_TOKEN

Check = Callable[[Headers], Awaitable[bool]]

# Shorter than this, a bearer token is guessable: the server doesn't start with it.
MIN_TOKEN_LENGTH = 32


class Auth:
    """ASGI middleware: an HTTP request that fails `check` gets `refused` and goes no further."""

    def __init__(self, app: ASGIApp, check: Check, refused: int) -> None:
        self.app = app
        self.check = check
        self.refused = refused

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
        elif scope["type"] != "http":
            # A websocket, left unaccepted: uvicorn closes it with a 403.
            return
        elif await self.check(Headers(scope=scope)):
            await self.app(scope, receive, send)
        else:
            await Response(status_code=self.refused)(scope, receive, send)


def guarded(app: ASGIApp) -> Auth:
    """`app` behind the check LIBRARIAN_AUTH names; without one complete, no server."""
    if AUTH == "bearer":
        if not BEARER_TOKEN or len(BEARER_TOKEN) < MIN_TOKEN_LENGTH:
            raise SystemExit(
                f"LIBRARIAN_AUTH is bearer: set LIBRARIAN_BEARER_TOKEN, {MIN_TOKEN_LENGTH} characters or more"
            )
        return Auth(app, _bearer(BEARER_TOKEN), 401)
    if AUTH == "access":
        if not ACCESS_TEAM or not ACCESS_AUD:
            raise SystemExit(
                "LIBRARIAN_AUTH is access: set LIBRARIAN_ACCESS_TEAM and LIBRARIAN_ACCESS_AUD"
            )
        # A bare 403: the WWW-Authenticate is Access's, its Managed OAuth sends one.
        return Auth(app, _access(ACCESS_TEAM, ACCESS_AUD), 403)
    raise SystemExit("set LIBRARIAN_AUTH to access or bearer")


def _bearer(token: str) -> Check:
    expected = f"Bearer {token}".encode()

    async def check(headers: Headers) -> bool:
        given = headers.get("authorization", "").encode()
        return hmac.compare_digest(given, expected)

    return check


def _access(team: str, aud: str) -> Check:
    issuer = f"https://{team}.cloudflareaccess.com"
    # Fetched on first use and cached; a kid it doesn't know refetches, so rotation needs nothing.
    keys = PyJWKClient(f"{issuer}/cdn-cgi/access/certs")

    def verified(token: str) -> bool:
        try:
            key = keys.get_signing_key_from_jwt(token)
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=aud,
                issuer=issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except Exception as error:  # noqa: BLE001
            # Whatever fails, a bad token or the keys not fetched, the request is refused.
            # The reason goes to the log, never the token: a wrong team shows up here.
            print(f"auth refused: {type(error).__name__}: {error}", file=sys.stderr)
            return False
        return True

    async def check(headers: Headers) -> bool:
        token = headers.get("cf-access-jwt-assertion")
        if token is None:
            print("auth refused: no Cf-Access-Jwt-Assertion", file=sys.stderr)
            return False
        # Off the event loop: fetching the keys is a blocking request.
        return await asyncio.to_thread(verified, token)

    return check
