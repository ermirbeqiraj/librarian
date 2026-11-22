using System.Text.Json;
using Application.Handlers.Ask;
using Application.Handlers.Ingest;
using Application.Ports.Ask;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;

namespace Adapters.Mistral;

public sealed class AskRunOptionsFactory(
    ISql sql,
    [FromKeyedServices("askChat")] IChatClient chat,
    AskOptions ask,
    LibrarianOptions paths) : IAskRunOptionsFactory
{
    public async Task<AgentRunOptions> CreateAsync(IList<AITool> tools, CancellationToken cancellationToken = default)
        => new ChatClientAgentRunOptions
        {
            ChatOptions = new ChatOptions { Instructions = await TextAsync(cancellationToken), Tools = [.. tools] },
        };

    // One raw model call, no loop behind it: the forced submit cannot ping-pong.
    public async Task<bool> ForceSubmitAsync(IReadOnlyList<ChatMessage> messages, AIFunction submit, CancellationToken cancellationToken = default)
    {
        var response = await chat.GetResponseAsync(messages, new ChatOptions
        {
            Instructions = await TextAsync(cancellationToken),
            Tools = [submit],
            ToolMode = ChatToolMode.RequireSpecific(AskHandler.Submit),
        }, cancellationToken);
        var call = response.Messages
            .SelectMany(message => message.Contents)
            .OfType<FunctionCallContent>()
            .FirstOrDefault(content => content.Name == AskHandler.Submit && content.CallId is not null);
        if (call is null)
            return false;
        await submit.InvokeAsync(new AIFunctionArguments(call.Arguments!), cancellationToken);
        return true;
    }

    private async Task<string> TextAsync(CancellationToken cancellationToken)
    {
        var library = await sql.LibraryAsync(cancellationToken);
        if (library.Error is not null)
            throw new InvalidOperationException($"The library query failed: {library.Error}");
        var schema = await sql.SchemaAsync(cancellationToken);
        var text = File.ReadAllText(ask.InstructionsPath);
        var context = Path.Combine(paths.Root, "context.md");
        text = text.Replace("{context}", File.Exists(context) ? File.ReadAllText(context).Trim() : "");
        text = text.Replace("{rounds}", ask.MaxRounds.ToString());
        text = text.Replace("{library}", JsonSerializer.Serialize(library.Rows, AskJson.Options));
        text = text.Replace("{schema}", Indented(schema));
        return text;
    }

    private static string Indented(Schema schema)
    {
        var options = new JsonSerializerOptions(AskJson.Options) { WriteIndented = true };
        return JsonSerializer.Serialize(schema, options);
    }
}
