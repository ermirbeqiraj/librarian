using System.Globalization;
using Librarian.Application.Ports.Retrieve;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Librarian.Adapters.Mistral;

public sealed class RefineRunOptionsFactory : IRefineRunOptionsFactory
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

    private static string InstructionsText()
    {
        var assembly = typeof(RefineRunOptionsFactory).Assembly;
        using var stream = assembly.GetManifestResourceStream("Librarian.Adapters.Mistral.Instructions.refine-v3.md")
            ?? throw new InvalidOperationException("refine-v3.md is not an embedded resource of Librarian.Adapters.");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd().Trim();
    }
}
