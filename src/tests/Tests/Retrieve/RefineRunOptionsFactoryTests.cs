using Adapters.Mistral;
using Microsoft.Agents.AI;

namespace Tests.Retrieve;

public sealed class RefineRunOptionsFactoryTests : IDisposable
{
    private readonly string path = Path.Combine(Path.GetTempPath(), $"refine-instructions-{Guid.NewGuid():N}.md");

    public RefineRunOptionsFactoryTests()
        => File.WriteAllText(path, "Oggi è {today} ({oggi}). Il \"period\" finisce a {today}.\n");

    public void Dispose()
        => File.Delete(path);

    private string Instructions(DateOnly today)
    {
        var runOptions = new RefineRunOptionsFactory(path).Create(today);
        var options = Assert.IsType<ChatClientAgentRunOptions>(runOptions);
        var instructions = options.ChatOptions?.Instructions;
        Assert.NotNull(instructions);
        return instructions;
    }

    [Fact]
    public void The_instructions_carry_today_and_oggi()
    {
        Assert.Contains("Oggi è 2026-11-11 (11 novembre 2026)", Instructions(new DateOnly(2026, 11, 11)));
        Assert.DoesNotContain("{today}", Instructions(new DateOnly(2026, 11, 11)));
        Assert.DoesNotContain("{oggi}", Instructions(new DateOnly(2026, 11, 11)));
    }

    [Fact]
    public void The_Italian_months_reach_december_and_a_january_today()
    {
        Assert.Contains("Oggi è 2026-12-05 (5 dicembre 2026)", Instructions(new DateOnly(2026, 12, 5)));
        Assert.Contains("Oggi è 2026-01-15 (15 gennaio 2026)", Instructions(new DateOnly(2026, 1, 15)));
    }

    [Fact]
    public void A_second_today_token_renders_the_same_day()
    {
        Assert.Contains("\"period\" finisce a 2026-11-11", Instructions(new DateOnly(2026, 11, 11)));
    }

    [Fact]
    public void Two_todays_render_two_instruction_sets()
    {
        var november = Instructions(new DateOnly(2026, 11, 11));
        var january = Instructions(new DateOnly(2026, 1, 15));
        Assert.NotEqual(november, january);
        Assert.DoesNotContain("2026-01-15", november);
    }
}
