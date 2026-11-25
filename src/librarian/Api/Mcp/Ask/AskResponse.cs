using System.Text.Json;

namespace Api.Mcp.Ask;

internal sealed record AskResponse(
    string Id,
    string Question,
    string Status,
    string Reasoning,
    List<AskValue> Values,
    List<AskSource> Sources,
    DateTime? CompletedAt);

internal sealed record AskValue(string Name, JsonElement Value, string? Unit, int Source);

internal sealed record AskSource(
    int Id,
    long DocumentId,
    string Kind,
    string? Section,
    long? SectionId,
    string? Quote,
    int? SectionChars,
    int? DocumentChars,
    string? File);
