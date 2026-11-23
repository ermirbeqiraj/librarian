using Api.Features.Auth;

using Microsoft.Extensions.Hosting;

namespace Api.Features.Whoami;

internal static class WhoamiEndpoints
{
    internal static IEndpointRouteBuilder MapWhoamiEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/whoami", (HttpContext http, IHostEnvironment environment) =>
        {
            var identity = http.User.Identity;
            return Results.Json(new WhoamiResponse(
                Mode: AuthOptions.ModeFor(environment),
                Scheme: identity?.AuthenticationType,
                Authenticated: identity is { IsAuthenticated: true },
                Identity: identity is { IsAuthenticated: true }
                    ? new WhoamiIdentity(
                        Sub: http.User.FindFirst("sub")?.Value,
                        Email: http.User.FindFirst("email")?.Value,
                        Name: identity.Name)
                    : null,
                Claims: [.. http.User.Claims.Select(claim => new WhoamiClaim(claim.Type, claim.Value))]));
        });
        return app;
    }
}
