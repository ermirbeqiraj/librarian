using Application.Handlers.Ingest;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Application.Ports.Ask;

public interface IAskRunOptionsFactory
{
    Task<AgentRunOptions> CreateAsync(IList<AITool> tools, CancellationToken cancellationToken = default);

    Task<bool> ForceSubmitAsync(IReadOnlyList<ChatMessage> messages, AIFunction submit, CancellationToken cancellationToken = default);
}
