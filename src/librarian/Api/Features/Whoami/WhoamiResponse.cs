namespace Api.Features.Whoami;

internal sealed record WhoamiResponse(
    string Mode,
    string? Scheme,
    bool Authenticated,
    WhoamiIdentity? Identity,
    IReadOnlyList<WhoamiClaim> Claims);

internal sealed record WhoamiIdentity(string? Sub, string? Email, string? Name);

internal sealed record WhoamiClaim(string Type, string Value);
