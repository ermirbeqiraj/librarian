using Adapters.Postgres;
using Application.Handlers.Ask;

namespace Tests.Ask;

public sealed class AskTests
{
    [Fact]
    public void The_sql_is_wrapped_as_a_capped_subquery()
    {
        Assert.Equal(
            """
            SELECT * FROM (
            SELECT kind FROM documents
            ) AS q LIMIT 201
            """,
            PostgresSql.Wrapped("SELECT kind FROM documents"));
        Assert.Equal(
            """
            SELECT * FROM (
            SELECT kind FROM documents
            ) AS q LIMIT 201
            """,
            PostgresSql.Wrapped(" SELECT kind FROM documents; "));
    }

    [Fact]
    public void The_query_fuel_builds_its_filters()
    {
        var filters = AskHandler.Filters([1, 2], "2025-01-01", "2025-12-31");
        Assert.Equal(new DateOnly(2025, 1, 1), filters!.Period!.From);
        Assert.Equal(new DateOnly(2025, 12, 31), filters.Period.To);
        Assert.Equal([1L, 2L], filters.DocumentIds);

        Assert.Null(AskHandler.Filters(null, null, null)!.Period);
    }

    [Fact]
    public void A_bad_day_is_rejected()
    {
        Assert.Throws<ArgumentException>(() => AskHandler.Filters(null, "2025-3-15", null));
        Assert.Throws<ArgumentException>(() => AskHandler.Filters(null, "mare", null));
    }

    [Fact]
    public void The_status_names_are_the_wire_ones()
    {
        Assert.Equal(AskStatus.Found, AskHandler.StatusOf("found"));
        Assert.Equal(AskStatus.Partial, AskHandler.StatusOf("partial"));
        Assert.Equal(AskStatus.NotFound, AskHandler.StatusOf("not_found"));
        Assert.Equal("found", AskHandler.Wire(AskStatus.Found));
        Assert.Equal("not_found", AskHandler.Wire(AskStatus.NotFound));
        Assert.Throws<ArgumentException>(() => AskHandler.StatusOf("maybe"));
    }
}
