using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Application.Domain;

namespace Application.Handlers.Ask;

public static class AskJson
{
    public static readonly JsonSerializerOptions Options = AskJsonContext.Default.Options;
}

public static class JsonArray
{
    public static string Of(IEnumerable<object> items)
    {
        using var stream = new MemoryStream();
        using var writer = new Utf8JsonWriter(stream);
        writer.WriteStartArray();
        foreach (var item in items)
            writer.WriteRawValue(JsonSerializer.SerializeToUtf8Bytes(item, item.GetType(), AskJson.Options), skipInputValidation: true);
        writer.WriteEndArray();
        writer.Flush();
        return Encoding.UTF8.GetString(stream.ToArray());
    }
}

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web)]
[JsonSerializable(typeof(AskResult))]
[JsonSerializable(typeof(AskedValue))]
[JsonSerializable(typeof(AskedSource))]
[JsonSerializable(typeof(AskedHit))]
[JsonSerializable(typeof(AskedSeen))]
[JsonSerializable(typeof(SubmittedValue))]
[JsonSerializable(typeof(SubmittedSource))]
[JsonSerializable(typeof(Ports.Ask.SqlResult))]
[JsonSerializable(typeof(List<long>))]
[JsonSerializable(typeof(List<SubmittedValue>))]
[JsonSerializable(typeof(List<SubmittedSource>))]
[JsonSerializable(typeof(Ports.Ask.Schema))]
public partial class AskJsonContext : JsonSerializerContext;

public enum AskStatus
{
    [JsonPropertyName("not_found")] NotFound,
    [JsonPropertyName("partial")] Partial,
    [JsonPropertyName("found")] Found,
}

public sealed class AskFailedException(string message) : DomainException(message);

public sealed record AskResult(
    string Id,
    string Question,
    AskStatus Status,
    string Reasoning,
    List<AskedValue> Values,
    List<AskedSource> Sources,
    DateTime? CompletedAt,
    string? Error);

public sealed record AskedValue(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("value")] JsonElement Value,
    [property: JsonPropertyName("unit")] string? Unit,
    [property: JsonPropertyName("source")] int Source);

public sealed record AskedSource(
    [property: JsonPropertyName("id")] int Id,
    [property: JsonPropertyName("document_id")] long DocumentId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("section")] string? Section,
    [property: JsonPropertyName("section_id")] long? SectionId,
    [property: JsonPropertyName("quote")] string? Quote,
    [property: JsonPropertyName("section_chars")] int? SectionChars,
    [property: JsonPropertyName("document_chars")] int? DocumentChars,
    [property: JsonPropertyName("file")] string? File);

public sealed record AskedHit(
    [property: JsonPropertyName("section_id")] long SectionId,
    [property: JsonPropertyName("document_id")] long DocumentId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("issuer")] string? Issuer,
    [property: JsonPropertyName("validity")] Validity Validity,
    [property: JsonPropertyName("heading")] string? Heading,
    [property: JsonPropertyName("text")] string Text);

public sealed record Validity(
    [property: JsonPropertyName("from")] string? From,
    [property: JsonPropertyName("to")] string? To);

public sealed record AskedSeen(
    [property: JsonPropertyName("section_id")] long SectionId,
    [property: JsonPropertyName("already_returned")] bool AlreadyReturned);

public sealed record Submitted(
    string Question,
    string Status,
    string Reasoning,
    List<SubmittedValue> Values,
    List<SubmittedSource> Sources);

public sealed record SubmittedValue(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("value")] JsonElement Value,
    [property: JsonPropertyName("unit")] string? Unit,
    [property: JsonPropertyName("source")] int Source);

public sealed record SubmittedSource(
    [property: JsonPropertyName("id")] int Id,
    [property: JsonPropertyName("document_id")] long DocumentId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("section")] string? Section,
    [property: JsonPropertyName("section_id")] long? SectionId,
    [property: JsonPropertyName("quote")] string? Quote);
