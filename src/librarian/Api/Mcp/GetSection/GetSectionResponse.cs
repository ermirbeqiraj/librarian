namespace Api.Mcp.GetSection;

internal sealed record GetSectionResponse(
    long SectionId,
    long DocumentId,
    string Kind,
    string? Heading,
    int Position,
    int Of,
    string Text,
    string? File);
