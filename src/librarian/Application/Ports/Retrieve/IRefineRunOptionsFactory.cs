using Microsoft.Agents.AI;

namespace Application.Ports.Retrieve;

public interface IRefineRunOptionsFactory
{
    AgentRunOptions Create(DateOnly today);
}
