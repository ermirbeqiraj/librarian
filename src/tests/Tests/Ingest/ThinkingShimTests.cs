using System.Text.Json.Nodes;
using Adapters.Mistral;

namespace Tests.Ingest;

public sealed class ThinkingShimTests
{
    [Fact]
    public void Deletes_thinking_parts_from_message_and_delta_contents()
    {
        var body = JsonNode.Parse("""
        {
          "choices": [
            { "message": { "content": [
                { "type": "thinking", "thinking": [{ "type": "text", "text": "considering the fields" }] },
                { "type": "text", "text": "{ \"kind\": \"invoice\" }" }
            ] } },
            { "delta": { "content": [
                { "type": "thinking", "thinking": [{ "type": "text", "text": "checking the amount" }] }
            ] } }
          ]
        }
        """)!;

        var changed = ThinkingShim.StripThinking(body);

        Assert.True(changed);
        var first = body["choices"]![0]!["message"]!["content"]!.AsArray();
        var text = Assert.Single(first);
        Assert.Equal("text", text!["type"]!.GetValue<string>());
        var second = body["choices"]![1]!["delta"]!["content"]!;
        Assert.Equal("", second.GetValue<string>());
    }

    [Fact]
    public void Leaves_a_response_without_thinking_untouched()
    {
        var body = JsonNode.Parse("""
        { "choices": [ { "message": { "content": [ { "type": "text", "text": "plain" } ] } } ] }
        """)!;

        Assert.False(ThinkingShim.StripThinking(body));
        var only = Assert.Single(body["choices"]![0]!["message"]!["content"]!.AsArray());
        Assert.Equal("plain", only!["text"]!.GetValue<string>());
    }
}
