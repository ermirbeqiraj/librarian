using Microsoft.Agents.AI;

namespace Application.Ports.Ingest;

public interface IExtractRunOptionsFactory
{
    AgentRunOptions Create(string text);
}
