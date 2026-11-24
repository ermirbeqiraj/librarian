namespace Api.Mcp.GetDocument;

internal sealed record GetDocumentResponse(
    long DocumentId,
    string Kind,
    string Description,
    CardValidity? Validity,
    int DocumentChars,
    List<MapEntry> Sections,
    string? File);

internal sealed record CardValidity(string? From, string? To, string? AsWritten);

internal sealed record MapEntry(long SectionId, int Position, string? Heading);
