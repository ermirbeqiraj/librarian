namespace Api.Mcp.Library;

internal sealed record LibraryResponse(int Documents, List<ShelfGroup> Groups);

internal sealed record ShelfGroup(string Kind, string? Issuer, int Documents, ShelfPeriod? Validity);

internal sealed record ShelfPeriod(string? From, string? To);
