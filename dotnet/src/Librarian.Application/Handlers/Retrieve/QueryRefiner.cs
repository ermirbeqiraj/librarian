using System.Text.Json;
using Librarian.Application.Ports.Retrieve;
using Microsoft.Agents.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Librarian.Application.Handlers.Retrieve;

public sealed class QueryRefiner(
    ILogger<QueryRefiner> logger,
    [FromKeyedServices("refineAgent")] AIAgent refineAgent,
    IRefineRunOptionsFactory refineRunOptionsFactory,
    RefineOptions refineOptions)
{
    public async Task<Refined> RefineAsync(string question, DateOnly today, CancellationToken cancellationToken = default)
    {
        var session = await refineAgent.CreateSessionAsync(cancellationToken);
        var runOptions = refineRunOptionsFactory.Create(today);
        var message = question;
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                var response = await refineAgent.RunAsync<Refined>(message, session, RefineJson.Options, runOptions, cancellationToken);
                var refined = response.Result;
                var problem = Problem(refined.Queries);
                if (problem is null)
                    return refined with { UserQuery = question };
                if (attempt >= refineOptions.ParseRetries)
                    throw new InvalidOperationException($"The refined answer for {question} does not fit the schema: {problem}");
                logger.LogWarning("The refine reply for {Question} did not fit the schema: {Problem}; asking again (attempt {Attempt})",
                    question, problem, attempt + 1);
                message = Feedback(problem);
            }
            catch (JsonException ex) when (attempt < refineOptions.ParseRetries)
            {
                logger.LogWarning("The refine reply for {Question} was not valid JSON: {Error}; asking again (attempt {Attempt})",
                    question, ex.Message, attempt + 1);
                message = Feedback(ex.Message);
            }
        }
    }

    private static string? Problem(List<RefinedQuery> queries)
    {
        if (queries.Count == 0)
            return "'queries' must hold at least one query.";
        for (var index = 0; index < queries.Count; index++)
        {
            var query = queries[index];
            if (string.IsNullOrWhiteSpace(query.Text))
                return $"queries[{index}].text must not be empty.";
            if (query.Period?.From is { } from && query.Period.To is { } to && from > to)
                return $"'from' {from:yyyy-MM-dd} is after 'to' {to:yyyy-MM-dd}";
        }
        return null;
    }

    private static string Feedback(string error)
    {
        return $"Your answer does not fit the schema:\n{error}\nFix it and return the whole object again.";
    }
}
