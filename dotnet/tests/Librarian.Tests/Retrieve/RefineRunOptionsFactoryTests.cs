using Librarian.Adapters.Mistral;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Librarian.Tests.Retrieve;

public sealed class RefineRunOptionsFactoryTests
{
    [Fact]
    public void The_instructions_carry_today_and_oggi()
    {
        var instructions = Instructions(new DateOnly(2026, 11, 11));
        Assert.Contains("Oggi è 2026-11-11 (11 novembre 2026)", instructions);
        Assert.DoesNotContain("{today}", instructions);
        Assert.DoesNotContain("{oggi}", instructions);
    }

    [Fact]
    public void The_Italian_months_reach_december_and_a_january_today()
    {
        Assert.Contains("Oggi è 2026-12-05 (5 dicembre 2026)", Instructions(new DateOnly(2026, 12, 5)));
        Assert.Contains("Oggi è 2026-01-15 (15 gennaio 2026)", Instructions(new DateOnly(2026, 1, 15)));
    }

    [Fact]
    public void The_last_example_s_today_is_filled_at_render_time()
    {
        Assert.Contains("\"to\": \"2026-11-11\"", Instructions(new DateOnly(2026, 11, 11)));
    }

    [Fact]
    public void Two_todays_render_two_instruction_sets()
    {
        var november = Instructions(new DateOnly(2026, 11, 11));
        var january = Instructions(new DateOnly(2026, 1, 15));
        Assert.NotEqual(november, january);
        Assert.DoesNotContain("2026-01-15", november);
    }

    private static string Instructions(DateOnly today)
    {
        var runOptions = new RefineRunOptionsFactory().Create(today);
        var options = Assert.IsType<ChatClientAgentRunOptions>(runOptions);
        var instructions = options.ChatOptions?.Instructions;
        Assert.NotNull(instructions);
        return instructions;
    }
}
