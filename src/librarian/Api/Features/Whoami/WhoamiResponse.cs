namespace Api.Features.Whoami;

internal sealed record WhoamiResponse(
    string Mode,
    string? Scheme,
    bool Authenticated,
    IReadOnlyList<WhoamiClaim> Claims);

internal sealed record WhoamiClaim(string Type, string Value);
