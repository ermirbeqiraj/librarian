using System.Text.Json;
using Librarian.Application.Handlers.Retrieve;
using Librarian.Application.Ports.Retrieve;

namespace Librarian.Tests.Retrieve;

public sealed class RefinedTests
{
    [Fact]
    public void The_wire_names_are_the_prompt_s_own()
    {
        var refined = JsonSerializer.Deserialize<Refined>(
            """
            {"user_query": "qnt ho speso di luce?", "queries": [
              {"text": "Quanto ho speso di luce?", "period": {"from": null, "to": "2026-03-31"}},
              {"text": "Quanto ho speso di telefono?", "period": null}
            ]}
            """,
            RefineJson.Options)!;

        Assert.Equal("qnt ho speso di luce?", refined.UserQuery);
        Assert.Null(refined.Queries[0].Period!.From);
        Assert.Equal(new DateOnly(2026, 3, 31), refined.Queries[0].Period!.To);
        Assert.Null(refined.Queries[1].Period);

        var json = JsonSerializer.Serialize(refined, RefineJson.Options);
        Assert.Contains("\"user_query\":\"qnt ho speso di luce?\"", json);
        Assert.Contains("\"period\":{\"from\":null,\"to\":\"2026-03-31\"}", json);
        Assert.Contains("\"period\":null", json);
    }

    [Fact]
    public void A_fake_date_is_a_parse_error()
    {
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize<Refined>(
            """
            {"user_query": "u", "queries": [{"text": "t", "period": {"from": "2026-02-30", "to": "2026-03-01"}}]}
            """,
            RefineJson.Options));
    }

    [Fact]
    public void A_missing_text_is_null_on_the_wire_and_caught_by_the_refiner()
    {
        var refined = JsonSerializer.Deserialize<Refined>(
            """
            {"user_query": "u", "queries": [{"period": null}]}
            """,
            RefineJson.Options)!;
        Assert.Null(refined.Queries[0].Text);
        Assert.Null(refined.Queries[0].Period);
    }

    [Fact]
    public void Open_periods_and_no_period_are_equal_only_to_themselves()
    {
        var january = new Period(new DateOnly(2026, 1, 1), new DateOnly(2026, 1, 31));
        Assert.Equal(new Period(new DateOnly(2026, 1, 1), new DateOnly(2026, 1, 31)), january);
        Assert.NotEqual(new Period(null, new DateOnly(2026, 1, 31)), new Period(new DateOnly(2026, 1, 1), null));
        Assert.Equal(new Period(null, null), new Period(null, null));
    }
}
