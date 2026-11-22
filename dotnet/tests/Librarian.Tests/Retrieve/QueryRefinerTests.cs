using System.Text.Json;
using Librarian.Application.Handlers.Retrieve;
using Librarian.Application.Ports.Retrieve;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging.Abstractions;

namespace Librarian.Tests.Retrieve;

public sealed class QueryRefinerTests
{
    private const string Question = "quanto ho pagato x gas nel 2026 e l acqua?";
    private static readonly DateOnly Today = new(2026, 11, 11);
    private const string ValidAnswer =
        """
        {"user_query": "not the question as it came", "queries": [
          {"text": "Quanto ho pagato per il gas nel 2026?", "period": {"from": "2026-01-01", "to": "2026-11-11"}},
          {"text": "Quanto ho pagato per l'acqua nel 2026?", "period": {"from": "2026-01-01", "to": null}}
        ]}
        """;

    [Fact]
    public async Task A_valid_answer_parses_and_the_question_as_it_came_is_kept_by_code()
    {
        var (client, refiner) = Build([ValidAnswer]);

        var refined = await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(Question, refined.UserQuery);
        Assert.Equal(2, refined.Queries.Count);
        Assert.Equal("Quanto ho pagato per il gas nel 2026?", refined.Queries[0].Text);
        Assert.Equal(new DateOnly(2026, 1, 1), refined.Queries[0].Period!.From);
        Assert.Equal(new DateOnly(2026, 11, 11), refined.Queries[0].Period!.To);
        Assert.Null(refined.Queries[1].Period!.To);
        var (_, options) = Assert.Single(client.Calls);
        Assert.Equal("instructions with 11 novembre 2026", options!.Instructions);
        Assert.IsType<ChatResponseFormatJson>(options.ResponseFormat);
    }

    [Fact]
    public async Task Bad_json_is_retried_with_the_parse_error_fed_back_on_the_same_session()
    {
        var (client, refiner) = Build(["{not json", ValidAnswer]);

        var refined = await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(Question, refined.UserQuery);
        Assert.Equal(2, client.Calls.Count);
        var second = client.Calls[1].Messages.ToList();
        Assert.Equal(ChatRole.User, second[0].Role);
        Assert.Equal(Question, second[0].Text);
        Assert.Equal(ChatRole.Assistant, second[1].Role);
        Assert.Equal("{not json", second[1].Text);
        Assert.Equal(ChatRole.User, second[^1].Role);
        Assert.StartsWith("Your answer does not fit the schema:", second[^1].Text);
        Assert.Contains("an invalid", second[^1].Text);
        Assert.EndsWith("Fix it and return the whole object again.", second[^1].Text);
    }

    [Fact]
    public async Task A_fake_date_is_retried_with_its_error_fed_back()
    {
        var answer = """
            {"user_query": "u", "queries": [{"text": "t", "period": {"from": "2026-02-30", "to": "2026-03-01"}}]}
            """;
        var (client, refiner) = Build([answer, ValidAnswer]);

        var refined = await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(Question, refined.UserQuery);
        Assert.Equal(2, client.Calls.Count);
        var feedback = client.Calls[1].Messages[^1].Text;
        Assert.Contains("period.from", feedback);
    }

    [Fact]
    public async Task A_query_without_a_text_is_retried()
    {
        var answer = """
            {"user_query": "u", "queries": [{"period": null}]}
            """;
        var (client, refiner) = Build([answer, ValidAnswer]);

        await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(2, client.Calls.Count);
        Assert.Contains("queries[0].text must not be empty.", client.Calls[1].Messages[^1].Text);
    }

    [Fact]
    public async Task A_period_with_from_after_to_is_retried()
    {
        var answer = """
            {"user_query": "u", "queries": [{"text": "t", "period": {"from": "2026-05-10", "to": "2026-05-01"}}]}
            """;
        var (client, refiner) = Build([answer, ValidAnswer]);

        var refined = await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(Question, refined.UserQuery);
        Assert.Equal(2, client.Calls.Count);
        Assert.Contains("'from' 2026-05-10 is after 'to' 2026-05-01", client.Calls[1].Messages[^1].Text);
    }

    [Fact]
    public async Task No_queries_at_all_is_retried()
    {
        var answer = """
            {"user_query": "u", "queries": []}
            """;
        var (client, refiner) = Build([answer, ValidAnswer]);

        await refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken);

        Assert.Equal(2, client.Calls.Count);
        Assert.Contains("'queries' must hold at least one query.", client.Calls[1].Messages[^1].Text);
    }

    [Fact]
    public async Task A_parse_error_past_the_retries_raises()
    {
        var (client, refiner) = Build(["{not json", "{not json", "{not json"], new RefineOptions { ParseRetries = 2 });

        await Assert.ThrowsAsync<JsonException>(
            () => refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken));

        Assert.Equal(3, client.Calls.Count);
    }

    [Fact]
    public async Task An_invalid_answer_past_the_retries_raises_a_readable_error()
    {
        var answer = """
            {"user_query": "u", "queries": [{"text": "t", "period": {"from": "2026-05-10", "to": "2026-05-01"}}]}
            """;
        var (client, refiner) = Build([answer, answer], new RefineOptions { ParseRetries = 1 });

        var error = await Assert.ThrowsAsync<InvalidOperationException>(
            () => refiner.RefineAsync(Question, Today, TestContext.Current.CancellationToken));

        Assert.Contains("'from' 2026-05-10 is after 'to' 2026-05-01", error.Message);
        Assert.Equal(2, client.Calls.Count);
    }

    private static (ScriptedChatClient Client, QueryRefiner Refiner) Build(string[] answers, RefineOptions? options = null)
    {
        var client = new ScriptedChatClient(answers);
        var agent = new ChatClientAgent(client, new ChatClientAgentOptions { Name = "refineAgent" });
        var refiner = new QueryRefiner(
            NullLogger<QueryRefiner>.Instance,
            agent,
            new FakeRunOptionsFactory(),
            options ?? new RefineOptions { ParseRetries = 2 });
        return (client, refiner);
    }

    private sealed class FakeRunOptionsFactory : IRefineRunOptionsFactory
    {
        public AgentRunOptions Create(DateOnly today)
        {
            return new ChatClientAgentRunOptions
            {
                ChatOptions = new ChatOptions { Instructions = $"instructions with {today.Day} novembre {today.Year}" },
            };
        }
    }
}
