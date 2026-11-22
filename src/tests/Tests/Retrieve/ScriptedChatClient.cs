using Microsoft.Extensions.AI;

namespace Tests.Retrieve;

internal sealed class ScriptedChatClient(params string[] answers) : IChatClient
{
    private readonly Queue<string> answers = new(answers);

    internal List<(IReadOnlyList<ChatMessage> Messages, ChatOptions? Options)> Calls { get; } = [];

    public Task<ChatResponse> GetResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options, CancellationToken cancellationToken = default)
    {
        Calls.Add((messages.ToList(), options));
        var answer = answers.Count > 0 ? answers.Dequeue() : throw new InvalidOperationException("The script ran out of answers.");
        return Task.FromResult(new ChatResponse([new ChatMessage(ChatRole.Assistant, answer)]));
    }

    public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options, CancellationToken cancellationToken = default)
        => throw new NotSupportedException();

    public object? GetService(Type serviceType, object? serviceKey = null)
        => serviceType == typeof(IChatClient) ? this : null;

    void IDisposable.Dispose()
    {
    }
}
