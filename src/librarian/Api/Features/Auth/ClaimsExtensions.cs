using System.Security.Claims;

namespace Api.Features.Auth;

internal static class ClaimsExtensions
{
    internal static string? Email(this ClaimsPrincipal principal) =>
        principal.FindFirst("email")?.Value;

    internal static string? Name(this ClaimsPrincipal principal) =>
        principal.FindFirst(claim => claim.Type is "name" or "common_name")?.Value;
}
