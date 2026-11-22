using System.Text.Json;
using System.Text.Json.Serialization;

namespace Application.Ports.Ask;

public interface ISql
{
    Task<SqlResult> RunAsync(string query, CancellationToken cancellationToken = default);

    Task<Schema> SchemaAsync(CancellationToken cancellationToken = default);

    Task<SqlResult> LibraryAsync(CancellationToken cancellationToken = default);
}

public sealed record SqlResult(List<string> Columns, List<Dictionary<string, JsonElement>> Rows, string? Error)
{
    public static SqlResult Failed(string error) => new([], [], error);
}

public sealed record Schema(
    [property: JsonPropertyName("tables")] List<Table> Tables,
    [property: JsonPropertyName("field_keys")] List<FieldKey> FieldKeys);

public sealed record Table(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("columns")] List<Column> Columns);

public sealed record Column(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("type")] string Type);

public sealed record FieldKey(
    [property: JsonPropertyName("key")] string Key,
    [property: JsonPropertyName("document_count")] int DocumentCount,
    [property: JsonPropertyName("kinds")] List<string> Kinds,
    [property: JsonPropertyName("example")] JsonElement Example);
