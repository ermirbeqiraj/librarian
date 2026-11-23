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
                Claims: [.. http.User.Claims.Select(claim => new WhoamiClaim(claim.Type, claim.Value))]));
        });
        return app;
    }
}
