using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Handlers.Retrieve;
using Librarian.Application.Ports.Ask;
using Librarian.Application.Ports.Retrieve;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Librarian.Application.Handlers.Ask;

public static class AskTrace
{
    public const string SourceName = "Librarian.Ask";
    public const string AskId = "librarian.ask_id";

    public static readonly ActivitySource Source = new(SourceName);
}

public sealed class AskHandler(
    ILogger<AskHandler> logger,
    LibrarianDbContext db,
    QueryRefiner refiner,
    ISql sql,
    IKeywordSearch keywordSearch,
    IVectorSearch vectorSearch,
    SectionSearch sectionSearch,
    [FromKeyedServices("askAgent")] AIAgent agent,
    IAskRunOptionsFactory runOptionsFactory,
    LibrarianOptions paths,
    AskOptions options)
{
    public const int Limit = 10;
    public const int MaxLimit = 50;
    public const string Submit = "submit";
    public const string Nudge = "This is the last round: call `submit` now with what you have found.";

    public async Task<AskResult> AskAsync(string question, CancellationToken cancellationToken = default)
    {
        using var bounded = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        bounded.CancelAfter(TimeSpan.FromSeconds(options.TimeoutSeconds));
        var ct = bounded.Token;
        var id = Guid.NewGuid().ToString("N");
        using var activity = AskTrace.Source.StartActivity();
        activity?.AddBaggage(AskTrace.AskId, id);

        var refined = await refiner.RefineAsync(question, DateOnly.FromDateTime(DateTime.Now), cancellationToken);
        var row = Domain.Ask.Create(id, question, JsonSerializer.Serialize(refined, RefineJson.Options), DateTime.UtcNow);
        db.Asks.Add(row);
        await db.SaveChangesAsync(cancellationToken);
        try
        {
            var submitted = await RunAsync(id, refined, ct);
            var result = await LinkAsync(submitted, ct);
            row.MarkCompleted(Wire(result.Status), JsonSerializer.Serialize(result, AskJson.Options), DateTime.UtcNow);
            await db.SaveChangesAsync(cancellationToken);
            logger.LogInformation("Ask {AskId} completed: {Status}, {Values} value(s), {Sources} source(s)",
                id, result.Status, result.Values.Count, result.Sources.Count);
            return result with { CompletedAt = row.CompletedAt };
        }
        catch (OperationCanceledException) when (bounded.IsCancellationRequested && !cancellationToken.IsCancellationRequested)
        {
            row.MarkFailed($"The ask timed out after {options.TimeoutSeconds}s.", DateTime.UtcNow);
            await db.SaveChangesAsync(CancellationToken.None);
            throw new TimeoutException($"The ask timed out after {options.TimeoutSeconds}s.");
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            row.MarkFailed(ex.Message, DateTime.UtcNow);
            await db.SaveChangesAsync(CancellationToken.None);
            throw;
        }
    }

    private async Task<(string Id, Submitted Submitted)> RunAsync(string id, Refined refined, CancellationToken ct)
    {
        var seen = new HashSet<long>();
        Submitted? submitted = null;

        async Task<string> RunSql(string query)
        {
            // FICC runs the loop silently; the tools speak for it in the trace instead.
            using var tool = AskTrace.Source.StartActivity("execute_tool sql");
            tool?.SetTag("arguments", query);
            return JsonSerializer.Serialize(await sql.RunAsync(query, ct), AskJson.Options);
        }

        async Task<string> KeywordAsync(string query, List<long>? documentIds = null, string? from = null, string? to = null, int limit = Limit)
        {
            using var tool = AskTrace.Source.StartActivity("execute_tool keyword_search");
            ToolTags(tool, query, documentIds, from, to, limit);
            var hits = await keywordSearch.SearchAsync(query, Filters(documentIds, from, to), Math.Clamp(limit, 1, MaxLimit), cancellationToken: ct);
            return JsonArray.Of(await sectionSearch.HitsAsync(hits, query, seen, cancellationToken: ct));
        }

        async Task<string> VectorAsync(string query, List<long>? documentIds = null, string? from = null, string? to = null, int limit = Limit)
        {
            using var tool = AskTrace.Source.StartActivity("execute_tool vector_search");
            ToolTags(tool, query, documentIds, from, to, limit);
            var hits = await vectorSearch.SearchAsync(query, Filters(documentIds, from, to), Math.Clamp(limit, 1, MaxLimit), cancellationToken: ct);
            return JsonArray.Of(await sectionSearch.HitsAsync(hits, query, seen, cancellationToken: ct));
        }

        string SubmitResult(string status, List<SubmittedValue> values, List<SubmittedPassage> passages, List<SubmittedSource> sources)
        {
            using var tool = AskTrace.Source.StartActivity("execute_tool submit");
            StatusOf(status);
            submitted = new Submitted(refined.UserQuery, status, values, passages, sources);
            return "ok";
        }

        var submit = AIFunctionFactory.Create(SubmitResult, new AIFunctionFactoryOptions { Name = Submit, Description = ToolText.Submit(), SerializerOptions = AskJson.Options });
        var tools = new List<AITool>
        {
            AIFunctionFactory.Create(RunSql, new AIFunctionFactoryOptions { Name = "sql", Description = ToolText.Sql(), SerializerOptions = AskJson.Options }),
            AIFunctionFactory.Create(KeywordAsync, new AIFunctionFactoryOptions { Name = "keyword_search", Description = ToolText.KeywordSearch(), SerializerOptions = AskJson.Options }),
            AIFunctionFactory.Create(VectorAsync, new AIFunctionFactoryOptions { Name = "vector_search", Description = ToolText.VectorSearch(), SerializerOptions = AskJson.Options }),
            submit,
        };
        var runOptions = await runOptionsFactory.CreateAsync(tools, ct);
        var session = await agent.CreateSessionAsync(ct);
        var run = await agent.RunAsync(new ChatMessage(ChatRole.User, JsonSerializer.Serialize(refined, RefineJson.Options)), session, runOptions, ct);
        if (submitted is null)
        {
            // The rounds are gone without a submit: one raw call forces it, and we invoke submit
            // ourselves — there is no loop behind the call to force it a second time.
            var history = new List<ChatMessage>(run.Messages) { new(ChatRole.User, Nudge) };
            var forced = await runOptionsFactory.ForceSubmitAsync(history, submit, ct);
            if (!forced)
                throw new InvalidOperationException("The ask agent ended without calling submit.");
        }
        return (id, submitted!);
    }

    private static void ToolTags(Activity? tool, string query, List<long>? documentIds, string? from, string? to, int limit)
    {
        if (tool is null)
            return;
        tool.SetTag("arguments", query);
        if (documentIds is not null)
            tool.SetTag("document_ids", string.Join(',', documentIds));
        if (from is not null)
            tool.SetTag("from", from);
        if (to is not null)
            tool.SetTag("to", to);
        tool.SetTag("limit", limit);
    }

    public static SearchFilters? Filters(List<long>? documentIds, string? from, string? to)
    {
        Period? period = null;
        if (from is not null || to is not null)
        {
            DateOnly? start = from is null ? null : Day(from, "from");
            DateOnly? end = to is null ? null : Day(to, "to");
            period = new Period(start, end);
        }
        return new SearchFilters(period, null, documentIds);
    }

    public static DateOnly Day(string value, string name)
        => DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var day)
            ? day
            : throw new ArgumentException($"The {name} '{value}' is not an ISO day (yyyy-MM-dd).");

    private async Task<AskResult> LinkAsync((string Id, Submitted Submitted) run, CancellationToken cancellationToken)
    {
        var submitted = run.Submitted;
        var documentIds = submitted.Sources.Select(source => source.DocumentId).Distinct().ToList();
        var files = await db.Ingestions
            .Where(i => i.DocumentId != null && documentIds.Contains(i.DocumentId.Value))
            .ToDictionaryAsync(i => i.DocumentId!.Value, i => i.FileName, cancellationToken);
        var sources = new List<AskedSource>();
        foreach (var source in submitted.Sources)
        {
            var file = (string?)null;
            if (options.FileUrl is not null && files.TryGetValue(source.DocumentId, out var name))
                file = options.FileUrl.Replace("{path}", Uri.EscapeDataString(Path.Combine(paths.ProcessedPath, name)));
            sources.Add(new AskedSource(source.Id, source.DocumentId, source.Kind, source.Section, source.SectionId, file));
        }
        return new AskResult(
            run.Id,
            submitted.Question,
            StatusOf(submitted.Status),
            [.. submitted.Values.Select(value => new AskedValue(value.Name, value.Value, value.Unit, value.Source))],
            [.. submitted.Passages.Select(passage => new AskedPassage(passage.Text, passage.Source))],
            sources,
            CompletedAt: null,
            Error: null);
    }

    public static AskStatus StatusOf(string status) => status switch
    {
        "found" => AskStatus.Found,
        "partial" => AskStatus.Partial,
        "not_found" => AskStatus.NotFound,
        _ => throw new ArgumentException($"The status '{status}' is not one of found, partial, not_found."),
    };

    public static string Wire(AskStatus status) => status switch
    {
        AskStatus.Found => "found",
        AskStatus.Partial => "partial",
        AskStatus.NotFound => "not_found",
        AskStatus.Error => "error",
        _ => throw new InvalidOperationException($"The status {status} has no wire name."),
    };
}
