using System.Globalization;
using Application.Ports.Retrieve;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Adapters.Mistral;

public sealed class RefineRunOptionsFactory(string instructionsPath) : IRefineRunOptionsFactory
{
    private static readonly string[] Months =
    [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ];

    public AgentRunOptions Create(DateOnly today)
    {
        var instructions = InstructionsText()
            .Replace("{today}", today.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture))
            .Replace("{oggi}", $"{today.Day} {Months[today.Month - 1]} {today.Year}");
        return new ChatClientAgentRunOptions
        {
            ChatOptions = new ChatOptions { Instructions = instructions },
        };
    }

    private string InstructionsText()
        => File.ReadAllText(instructionsPath).Trim();
}
