using Microsoft.Agents.AI;

namespace Librarian.Application.Ports.Ingest;

public interface IExtractRunOptionsFactory
{
    AgentRunOptions Create(string text);
}
