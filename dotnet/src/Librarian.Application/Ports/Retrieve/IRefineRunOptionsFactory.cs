using Microsoft.Agents.AI;

namespace Librarian.Application.Ports.Retrieve;

public interface IRefineRunOptionsFactory
{
    AgentRunOptions Create(DateOnly today);
}
