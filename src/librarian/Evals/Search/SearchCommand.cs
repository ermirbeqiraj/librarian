using System.Diagnostics;
using Application.Domain;
using Application.Handlers.Store;
using Application.Ports.Retrieve;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI.Evaluation;
using Microsoft.Extensions.DependencyInjection;

namespace Evals.Search;

public static class SearchCommand
{
    public static async Task<int> RunAsync(IServiceProvider services, string[] args)
    {
        var mode = ParseFlag(args, "--mode");
        if (mode is not ("vector" or "keyword"))
        {
            Console.Error.WriteLine("usage: Evals search --mode vector|keyword [--limit N]");
            return 2;
        }
        var limit = int.TryParse(ParseFlag(args, "--limit"), out var parsed) && parsed > 0 ? parsed : 5;

        var options = services.GetRequiredService<EvalsOptions>();
        var cases = SearchCase.Load(Path.Combine(options.Root, "search"));
        if (cases.Count == 0)
        {
            Console.Error.WriteLine("No cases in the search folder.");
            return 2;
        }

        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
        var sections = await db.Set<Section>().AsNoTracking()
            .Select(s => new { s.Id, s.Text }).ToListAsync();
        var chunks = await db.Set<Chunk>().AsNoTracking()
            .Select(c => new { c.Id, c.SectionId, c.Text }).ToListAsync();
        if (sections.Count == 0)
        {
            Console.Error.WriteLine("The library is empty: no sections. Inject first.");
            return 2;
        }

        var sectionText = sections.ToDictionary(s => s.Id, s => Text.Squeeze(s.Text));
        var chunkText = chunks.ToDictionary(c => c.Id, c => Text.Squeeze(c.Text));
        var documents = await db.Set<Document>().CountAsync();

        List<SearchCase> runnable = [];
        var skipped = new List<SearchCase>();
        List<(string File, int Index, string Quote)> partialMissing = [];
        foreach (var @case in cases)
        {
            var missing = @case.Quotes.Where(quote =>
                !sectionText.Values.Any(text => text.Contains(Text.Squeeze(quote)))).ToList();
            if (missing.Count == @case.Quotes.Count)
                skipped.Add(@case);
            else
            {
                runnable.Add(@case);
                if (missing.Count > 0)
                    partialMissing.Add((@case.FileName, @case.Index, missing[0]));
            }
        }

        Console.WriteLine($"Search eval — mode: {mode}, limit: {limit}");
        Console.WriteLine($"cases: {cases.Count} · runnable: {runnable.Count} · skipped: {skipped.Count}");
        Console.WriteLine();
        Console.WriteLine($"{"#",-4} {"file",-14} {"author",-8} {"chunk",-6} {"section",-8} {"1-chunk",8}  question");

        var results = new List<(SearchCase Case, EvaluationResult Metrics)>();
        var watch = Stopwatch.StartNew();
        foreach (var @case in runnable)
            results.Add((@case, await EvaluateAsync(scope, mode!, @case, limit, sectionText, chunkText)));
        watch.Stop();

        foreach (var (caseInfo, metrics) in results)
        {
            var chunkRank = (int)metrics.Get<NumericMetric>(Metrics.ChunkRank).Value!;
            var sectionRank = (int)metrics.Get<NumericMetric>(Metrics.SectionRank).Value!;
            var oneChunk = metrics.Get<BooleanMetric>(Metrics.OneChunk).Value is true;
            Console.WriteLine(
                $"{caseInfo.Index,-4} {Short(caseInfo.FileName, 14),-14} {caseInfo.Author,-8} {chunkRank,-6} {sectionRank,-8} {(oneChunk ? "yes" : "no"),8}  {Short(caseInfo.Query, 46)}");
        }

        var totals = Compute(results);
        Console.WriteLine();
        Console.WriteLine(PrintedSummary(results, totals, watch.Elapsed));
        if (partialMissing.Count > 0)
            foreach (var missing in partialMissing)
                Console.WriteLine($"note: a quote is missing from the library: {missing.File} #{missing.Index} — \"{Short(missing.Quote, 56)}\"");
        foreach (var @case in skipped)
            Console.WriteLine($"skipped: content missing: {@case.FileName} #{@case.Index} — {Short(@case.Query, 46)}");

        var store = services.GetRequiredService<StoreOptions>();
        var (name, record) = RunRecord.Build(
            mode!, limit, store.Embedding.Model, documents, sections.Count, chunks.Count,
            results, skipped, partialMissing, totals, watch.Elapsed);
        var runs = Path.Combine(options.Root, "search", "runs");
        Directory.CreateDirectory(runs);
        await File.WriteAllTextAsync(Path.Combine(runs, name), record);
        Console.WriteLine();
        Console.WriteLine($"run record: {Path.Combine(runs, name)}");
        return 0;
    }

    private static async Task<EvaluationResult> EvaluateAsync(
        IServiceScope scope, string mode, SearchCase @case, int limit,
        Dictionary<long, string> sectionText, Dictionary<long, string> chunkText)
    {
        var filters = new SearchFilters(Period: @case.Period);
        IReadOnlyList<ChunkHit> hits = mode == "vector"
            ? await scope.ServiceProvider.GetRequiredService<IVectorSearch>().SearchAsync(@case.Query, filters, limit)
            : await scope.ServiceProvider.GetRequiredService<IKeywordSearch>().SearchAsync(@case.Query, filters, limit);

        var quotes = @case.Quotes.Select(Text.Squeeze).ToList();
        var chunkRank = 0;
        var sectionRank = 0;
        string? chunkReason = null;
        string? sectionReason = null;
        foreach (var hit in hits.OrderBy(h => h.Rank))
        {
            if (chunkRank == 0)
                FindQuote(chunkText[hit.ChunkId], quotes, hit.Rank, ref chunkRank, ref chunkReason);
            if (sectionRank == 0)
                FindQuote(sectionText[hit.SectionId], quotes, hit.Rank, ref sectionRank, ref sectionReason);
        }

        var oneChunk = false;
        string? oneChunkReason = null;
        foreach (var (chunkId, text) in chunkText)
        {
            foreach (var quote in quotes)
            {
                if (text.Contains(quote))
                {
                    oneChunk = true;
                    oneChunkReason = $"chunk {chunkId}";
                    break;
                }
            }
            if (oneChunk)
                break;
        }

        return new EvaluationResult(
            new NumericMetric(Metrics.ChunkRank, chunkRank, chunkReason),
            new NumericMetric(Metrics.SectionRank, sectionRank, sectionReason),
            new BooleanMetric(Metrics.OneChunk, oneChunk, oneChunkReason));
    }

    private static void FindQuote(string squeezed, List<string> quotes, long rank, ref int foundRank, ref string? reason)
    {
        foreach (var quote in quotes)
            if (squeezed.Contains(quote))
            {
                foundRank = (int)rank;
                reason = $"hit {rank}: \"{quote}\"";
                return;
            }
    }

    private static Totals Compute(List<(SearchCase Case, EvaluationResult Metrics)> results) =>
        new(
            results.Count(r => r.Metrics.Get<NumericMetric>(Metrics.SectionRank).Value is 1),
            results.Count(r => r.Metrics.Get<NumericMetric>(Metrics.SectionRank).Value is > 0 and <= 5),
            results.Count(r => r.Metrics.Get<NumericMetric>(Metrics.ChunkRank).Value is 1),
            results.Count(r => r.Metrics.Get<NumericMetric>(Metrics.ChunkRank).Value is > 0 and <= 5),
            results.Count(r => r.Metrics.Get<BooleanMetric>(Metrics.OneChunk).Value is true),
            results.Count);

    private static string PrintedSummary(List<(SearchCase Case, EvaluationResult Metrics)> results, Totals totals, TimeSpan elapsed)
    {
        var lines = new List<string>
        {
            $"section: top-1 {totals.SectionTop1}/{totals.Count} · top-5 {totals.SectionTop5}/{totals.Count}",
            $"chunk:   top-1 {totals.ChunkTop1}/{totals.Count} · top-5 {totals.ChunkTop5}/{totals.Count}",
            $"one-chunk: {totals.OneChunk}/{totals.Count}",
        };
        foreach (var group in results.GroupBy(r => r.Case.Author).OrderBy(g => g.Key))
        {
            var top1 = group.Count(r => r.Metrics.Get<NumericMetric>(Metrics.SectionRank).Value is 1);
            lines.Add($"by author {group.Key}: top-1 {top1}/{group.Count()}");
        }
        lines.Add($"elapsed: {elapsed.TotalSeconds:F1}s");
        return string.Join(Environment.NewLine, lines);
    }

    private static string? ParseFlag(string[] args, string name)
    {
        for (var i = 0; i < args.Length - 1; i++)
            if (args[i] == name)
                return args[i + 1];
        return null;
    }

    private static string Short(string text, int width) =>
        text.Length <= width ? text : text[..width] + "…";
}
