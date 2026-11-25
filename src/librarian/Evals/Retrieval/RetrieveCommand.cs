using System.Diagnostics;
using System.Text.Json;
using Application.Domain;
using Application.Handlers.Ask;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Evals.Retrieval;

internal sealed record Marks(bool? Answer, bool Honesty)
{
    public static Marks Of(RetrieveCase @case, AskResult result)
    {
        bool? answer = null;
        if (@case.AnswerValue is { } value)
            answer = Matching.AnySameValue(value, @case.Unit, result.Values);
        else if (@case.Quotes.Count > 0)
            answer = @case.Quotes.Any(quote => Matching.ContainsQuote(quote, result.Sources));
        var honesty = AskHandler.Wire(result.Status) == @case.ExpectedStatus;
        return new Marks(answer, honesty);
    }

    public bool Hit => Honesty && Answer is not false;
}

internal sealed class RetrieveCommand
{
    public static async Task<int> RunAsync(IServiceProvider services, string[] args)
    {
        if (ParseCases(args) is not { } parsed)
        {
            Console.Error.WriteLine("usage: Evals retrieval [--cases <file>] [--only <index>]");
            return 2;
        }

        var options = services.GetRequiredService<EvalsOptions>();
        var cases = RetrieveCase.Load(Path.Combine(options.Root, "retrieval"), parsed.File.Length > 0 ? parsed.File : null);
        if (parsed.Only is { } only)
        {
            if (parsed.File.Length == 0)
            {
                Console.Error.WriteLine("--only needs --cases: the index is per file.");
                return 2;
            }
            cases = [.. cases.Where(@case => @case.Index == only)];
        }
        if (cases.Count == 0)
        {
            Console.Error.WriteLine("No cases to run.");
            return 2;
        }

        using (var check = services.CreateScope())
        {
            var db = check.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            if (await db.Documents.CountAsync() == 0)
            {
                Console.Error.WriteLine("The library is empty: no documents. Inject first.");
                return 2;
            }
        }

        var askOptions = services.GetRequiredService<AskOptions>();
        Console.WriteLine($"Retrieval eval — model: {askOptions.Model}, reasoning: {askOptions.ReasoningEffort}, prompt: {askOptions.Instructions}, cases: {cases.Count}");
        Console.WriteLine();

        var results = new (RetrieveCase Case, AskResult? Result, Marks? Marks, string? Error)?[cases.Count];
        var print = new object();
        var watch = Stopwatch.StartNew();
        // All cases at once: a case is minutes of serial model calls, so the wall time is
        // the longest case, not their sum; too many at once would hit the model's rate limit.
        var indexed = cases.Select((@case, index) => (@case, index));
        await Parallel.ForEachAsync(indexed, new ParallelOptions { MaxDegreeOfParallelism = cases.Count }, async (item, _) =>
        {
            var (@case, index) = item;
            using var scope = services.CreateScope();
            var handler = scope.ServiceProvider.GetRequiredService<AskHandler>();
            try
            {
                var result = await handler.AskAsync(@case.Question);
                var marks = Marks.Of(@case, result);
                results[index] = (@case, result, marks, null);
                lock (print)
                    Print(@case, result, marks);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                results[index] = (@case, null, null, ex.Message);
                lock (print)
                    Console.WriteLine($"skipped: {@case.FileName} #{@case.Index}: {Short(ex.Message, 80)}");
            }
        });
        var ordered = results.Select(entry => entry!.Value).ToList();
        var spans = await SpansAsync(services, ordered);
        watch.Stop();

        Console.WriteLine();
        Console.WriteLine(Summary(ordered, watch.Elapsed));
        if (ordered.Count == 1 && ordered[0].Result is { } single)
            Timeline(single.Id, spans[single.Id]);

        var (name, record) = RunRecord.Build(askOptions, ordered, spans, watch.Elapsed);
        var runs = Path.Combine(options.Root, "retrieval", "runs");
        Directory.CreateDirectory(runs);
        await File.WriteAllTextAsync(Path.Combine(runs, name), record);
        Console.WriteLine();
        Console.WriteLine($"run record: {Path.Combine(runs, name)}");
        return results.Length == 0 ? 2 : 0;
    }

    private static async Task<Dictionary<string, List<string>>> SpansAsync(
        IServiceProvider services, List<(RetrieveCase Case, AskResult? Result, Marks? Marks, string? Error)> results)
    {
        var byAsk = new Dictionary<string, List<string>>();
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
        foreach (var id in results.Where(r => r.Result is not null).Select(r => r.Result!.Id).Distinct())
        {
            byAsk[id] = await db.Set<AskSpan>().AsNoTracking()
                .Where(span => span.AskId == id)
                .OrderBy(span => span.Id)
                .Select(span => span.Span)
                .ToListAsync();
        }
        return byAsk;
    }

    private static void Timeline(string askId, List<string> spans)
    {
        Console.WriteLine();
        Console.WriteLine($"ask {askId} — {spans.Count} spans:");
        foreach (var span in spans)
        {
            using var doc = JsonDocument.Parse(span);
            var root = doc.RootElement;
            var name = root.GetProperty("name").GetString();
            var ms = root.GetProperty("ms").GetInt64();
            Console.WriteLine($"  {ms / 1000.0,7:F1}s  {name}");
        }
    }

    private static void Print(RetrieveCase @case, AskResult result, Marks marks)
    {
        var hit = marks.Hit ? "hit" : "MISS";
        var answer = marks.Answer is null ? " - " : marks.Answer is true ? "ok " : "FAIL";
        var honesty = marks.Honesty ? "ok" : "HONESTY";
        Console.WriteLine($"{hit} {answer} {honesty}  {@case.FileName} #{@case.Index}  {AskHandler.Wire(result.Status)}  {Short(@case.Question, 52)}");
        if (@case.Note is not null)
            Console.WriteLine($"  note: {@case.Note}");
    }

    private static string Summary(List<(RetrieveCase Case, AskResult? Result, Marks? Marks, string? Error)> results, TimeSpan elapsed)
    {
        var scored = results.Where(r => r.Marks is not null).ToList();
        var hits = scored.Count(r => r.Marks!.Hit);
        var honest = scored.Count(r => r.Marks!.Honesty);
        var answered = scored.Where(r => r.Marks!.Answer is not null).ToList();
        var answers = answered.Count(r => r.Marks!.Answer is true);
        return $"hit {hits}/{scored.Count} · answer {answers}/{answered.Count} · honesty {honest}/{scored.Count} · skipped {results.Count - scored.Count} · elapsed: {elapsed.TotalSeconds:F1}s";
    }

    private static (string File, int? Only)? ParseCases(string[] args)
    {
        var file = "";
        int? only = null;
        for (var index = 0; index < args.Length; index++)
        {
            if (args[index] == "--cases")
            {
                if (index + 1 >= args.Length)
                    return null;
                file = args[++index];
                continue;
            }
            if (args[index] == "--only")
            {
                if (index + 1 >= args.Length || !int.TryParse(args[++index], out var number) || number < 0)
                    return null;
                only = number;
                continue;
            }
            return null;
        }
        return (file, only);
    }

    private static string Short(string text, int width)
        => text.Length <= width ? text : text[..width] + "…";
}
