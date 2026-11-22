using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Tests.Ingest;

public sealed class
    AgentRunOptionsMergeTests
{
    private sealed class RecordingChatClient : IChatClient
    {
        public ChatOptions? LastOptions { get; private set; }

        public Task<ChatResponse> GetResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options, CancellationToken cancellationToken = default)
        {
            LastOptions = options;
            return Task.FromResult(new ChatResponse([new ChatMessage(ChatRole.Assistant, "ok")]));
        }

        public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options, CancellationToken cancellationToken = default)
            => throw new NotSupportedException();

        public object? GetService(Type serviceType, object? serviceKey = null)
            => serviceType == typeof(IChatClient) ? this : null;

        void IDisposable.Dispose()
        {
        }
    }

    private static AIFunction Tool(string name) => AIFunctionFactory.Create(() => { }, new AIFunctionFactoryOptions { Name = name });

    [Fact]
    public async Task Tools_passed_in_the_run_options_reach_the_wire_with_the_fixed_instructions_intact()
    {
        var recording = new RecordingChatClient();
        var agent = new ChatClientAgent(recording, new ChatClientAgentOptions
        {
            Name = "extractAgent",
            ChatOptions = new ChatOptions { Instructions = "the fixed instructions", Tools = [Tool("fixedTool")] },
        });

        var runOptions = new ChatClientAgentRunOptions { ChatOptions = new ChatOptions { Tools = [Tool("runTool")] } };
        await agent.RunAsync("hello", null, runOptions, TestContext.Current.CancellationToken);

        var wireTools = recording.LastOptions!.Tools!.Select(t => ((AIFunction)t).Name).ToList();
        Assert.Contains("runTool", wireTools);
        Assert.Equal("the fixed instructions", recording.LastOptions.Instructions);
    }
}
