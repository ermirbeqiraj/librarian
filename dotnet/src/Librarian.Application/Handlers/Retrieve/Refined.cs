using System.Text.Json;
using System.Text.Json.Serialization;
using Librarian.Application.Ports.Retrieve;

namespace Librarian.Application.Handlers.Retrieve;

public static class RefineJson
{
    public static readonly JsonSerializerOptions Options = RefineJsonContext.Default.Options;
}

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web)]
[JsonSerializable(typeof(Refined))]
[JsonSerializable(typeof(RefinedQuery))]
[JsonSerializable(typeof(Period))]
public partial class RefineJsonContext : JsonSerializerContext;

public sealed record Refined(
    [property: JsonPropertyName("user_query")] string UserQuery,
    List<RefinedQuery> Queries);

public sealed record RefinedQuery(
    [property: JsonPropertyName("text")] string Text,
    [property: JsonPropertyName("period")] Period? Period);
