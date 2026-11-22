using System.Diagnostics;
using Librarian.Application.Handlers.Retrieve;
using Microsoft.Extensions.AI.Evaluation;
using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Evals.Refine;

public static class RefineCommand
{
    public static async Task<int> RunAsync(IServiceProvider services, string[] args)
    {
        if (args.Length > 0)
        {
            Console.Error.WriteLine("usage: Librarian.Evals refine");
            return 2;
        }

        var options = services.GetRequiredService<EvalsOptions>();
        var refineOptions = services.GetRequiredService<RefineOptions>();
        var refiner = services.GetRequiredService<QueryRefiner>();

        var cases = RefineCase.Load(Path.Combine(options.Root, "refine"));
        if (cases.Count == 0)
        {
            Console.Error.WriteLine("No cases in the refine folder.");
            return 2;
        }

        Console.WriteLine($"Refine eval — model: {refineOptions.Model}, cases: {cases.Count}");
        Console.WriteLine();

        var results = new List<(RefineCase Case, Refined Produced, EvaluationResult Metrics)>();
        var watch = Stopwatch.StartNew();
        foreach (var @case in cases)
        {
            var produced = await refiner.RefineAsync(@case.Question, @case.Today);
            var metrics = Evaluate(@case, produced);
            results.Add((@case, produced, metrics));
            Print(@case, produced, metrics);
        }
        watch.Stop();

        var totals = Compute(results);
        Console.WriteLine();
        Console.WriteLine(PrintedSummary(totals, watch.Elapsed));

        var (name, record) = RunRecord.Build(refineOptions.Model, results, totals, watch.Elapsed);
        var runs = Path.Combine(options.Root, "refine", "runs");
        Directory.CreateDirectory(runs);
        await File.WriteAllTextAsync(Path.Combine(runs, name), record);
        Console.WriteLine();
        Console.WriteLine($"run record: {Path.Combine(runs, name)}");
        return 0;
    }

    private static EvaluationResult Evaluate(RefineCase @case, Refined produced)
    {
        var metrics = new List<EvaluationMetric>
        {
            new BooleanMetric(Metrics.QueryCount, produced.Queries.Count == @case.Queries.Count,
                $"produced {produced.Queries.Count}, expected {@case.Queries.Count}"),
        };
        var pairs = Math.Max(@case.Queries.Count, produced.Queries.Count);
        for (var index = 0; index < pairs; index++)
        {
            if (index >= @case.Queries.Count)
                break;
            var expected = @case.Queries[index].Period;
            var producedPeriod = index < produced.Queries.Count ? produced.Queries[index].Period : null;
            metrics.Add(new BooleanMetric(Metrics.PeriodOk(index), expected == producedPeriod,
                $"expected {Text.Period(expected)}, got {Text.Period(producedPeriod)}"));
        }
        return new EvaluationResult([.. metrics]);
    }

    private static void Print(RefineCase @case, Refined produced, EvaluationResult metrics)
    {
        var mark = metrics.Get<BooleanMetric>(Metrics.QueryCount).Value is true ? "ok" : "COUNT";
        Console.WriteLine($"{@case.Question}  [queries {produced.Queries.Count}/{@case.Queries.Count} {mark}]");
        if (@case.Note is not null)
            Console.WriteLine($"  note: {@case.Note}");
        var pairs = Math.Max(@case.Queries.Count, produced.Queries.Count);
        for (var index = 0; index < pairs; index++)
        {
            var expectedText = index < @case.Queries.Count ? @case.Queries[index].Text : null;
            var producedText = index < produced.Queries.Count ? produced.Queries[index].Text : null;
            var expectedPeriod = index < @case.Queries.Count ? @case.Queries[index].Period : null;
            var producedPeriod = index < produced.Queries.Count ? produced.Queries[index].Period : null;
            var periodMark = index < @case.Queries.Count && metrics.Get<BooleanMetric>(Metrics.PeriodOk(index)).Value is true ? "ok" : "PERIOD";
            Console.WriteLine($"  {periodMark} {Text.Period(expectedPeriod)} -> {Text.Period(producedPeriod)}");
            Console.WriteLine($"    expected: {expectedText}");
            Console.WriteLine($"    got:      {producedText}");
        }
    }

    private static Totals Compute(List<(RefineCase Case, Refined Produced, EvaluationResult Metrics)> results) => new(
        results.Count,
        results.Count(r => r.Metrics.Get<BooleanMetric>(Metrics.QueryCount).Value is true),
        results.Sum(r => Enumerable.Range(0, r.Case.Queries.Count)
            .Count(index => r.Metrics.Get<BooleanMetric>(Metrics.PeriodOk(index)).Value is true)),
        results.Sum(r => r.Case.Queries.Count));

    private static string PrintedSummary(Totals totals, TimeSpan elapsed)
    {
        return $"query count: {totals.QueryCountOk}/{totals.Cases} · periods: {totals.PeriodsOk}/{totals.Periods} · elapsed: {elapsed.TotalSeconds:F1}s";
    }
}
