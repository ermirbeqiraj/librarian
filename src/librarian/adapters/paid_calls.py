"""The cap on the paid model calls one document may make, counted at the httpx client."""

import httpx


class PaidCallsSpent(Exception):
    pass


class PaidCalls:
    """Counts the requests an httpx client sends, its own retries included, and stops the one
    past the cap."""

    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.count = 0

    def spend(self, request: httpx.Request) -> None:
        if self.count == self.cap:
            raise PaidCallsSpent(f"{self.cap} paid calls spent, the cap for one document")
        self.count += 1

    def watch(self, client: httpx.Client) -> None:
        client.event_hooks["request"].append(self.spend)
