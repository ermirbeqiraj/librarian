using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Librarian.Adapters.Mistral;

public sealed class ThinkingShim : DelegatingHandler
{
    public ThinkingShim() : base(new SocketsHttpHandler())
    {
    }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var response = await base.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode || response.Content is null)
            return response;

        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!body.Contains("\"thinking\"", StringComparison.Ordinal))
            return response;

        try
        {
            var json = JsonNode.Parse(body);
            if (json is null || !StripThinking(json))
                return response;
            response.Content = new StringContent(json!.ToJsonString(), Encoding.UTF8, "application/json");
        }
        catch (JsonException)
        {
            return response;
        }
        return response;
    }

    public static bool StripThinking(JsonNode root)
    {
        if (root["choices"]?.AsArray() is not { } choices)
            return false;
        var changed = false;
        foreach (var choice in choices)
        {
            changed |= StripContent(choice?["message"]);
            changed |= StripContent(choice?["delta"]);
        }
        return changed;
    }

    private static bool StripContent(JsonNode? holder)
    {
        if (holder?["content"]?.AsArray() is not { } parts)
            return false;
        var changed = false;
        for (var i = parts.Count - 1; i >= 0; i--)
        {
            if (parts[i]?["type"]?.GetValue<string>() == "thinking")
            {
                parts.RemoveAt(i);
                changed = true;
            }
        }
        if (changed && parts.Count == 0)
            holder["content"] = string.Empty;
        return changed;
    }
}
