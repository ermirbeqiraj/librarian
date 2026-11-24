using System.Text.Json;
using System.Text.Json.Serialization;
using Api.Mcp.Ask;
using Api.Mcp.GetDocument;
using Api.Mcp.GetSection;
using Api.Mcp.Library;
using ModelContextProtocol.Protocol;

namespace Api.Mcp;

public static class McpJson
{
    public static readonly JsonSerializerOptions Options = McpJsonContext.Default.Options;
}

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web, PropertyNamingPolicy = JsonKnownNamingPolicy.SnakeCaseLower)]
[JsonSerializable(typeof(AskResponse))]
[JsonSerializable(typeof(GetSectionResponse))]
[JsonSerializable(typeof(GetDocumentResponse))]
[JsonSerializable(typeof(LibraryResponse))]
internal partial class McpJsonContext : JsonSerializerContext;

internal static class Results
{
    internal static CallToolResult Answer<T>(T response)
        => new()
        {
            Content = [new TextContentBlock { Text = JsonSerializer.Serialize(response, McpJson.Options) }],
        };

    internal static CallToolResult Error(string message)
        => new()
        {
            IsError = true,
            Content = [new TextContentBlock { Text = message }],
        };
}
