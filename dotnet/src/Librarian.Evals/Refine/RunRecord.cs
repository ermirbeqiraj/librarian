using System.Text.Json;
using Librarian.Application.Ports.Retrieve;
using Librarian.Evals.Common;
using Microsoft.Extensions.AI.Evaluation;

namespace Librarian.Evals.Refine;

internal static class RunRecord
{
    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static (string Name, string Record) Build(
        string model,
        List<(RefineCase Case, Application.Handlers.Retrieve.Refined Produced, EvaluationResult Metrics)> results,
        Totals totals,
        TimeSpan elapsed)
    {
        var name = $"run-{DateTime.Now:yyyy-MM-ddTHH-mm-ss}-refine.json";
        var record = new
        {
            RanAt = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            Commit = Git.FindSha(),
            Model = model,
            Cases = results.Select(r => new
            {
                File = r.Case.FileName,
                Index = r.Case.Index,
                Author = r.Case.Author,
                Note = r.Case.Note,
                Question = r.Case.Question,
                Today = r.Case.Today.ToString("yyyy-MM-dd"),
                UserQuery = r.Produced.UserQuery,
                ExpectedCount = r.Case.Queries.Count,
                ProducedCount = r.Produced.Queries.Count,
                CountOk = r.Metrics.Get<BooleanMetric>(Metrics.QueryCount).Value,
                CountReason = r.Metrics.Get<BooleanMetric>(Metrics.QueryCount).Reason,
                Queries = Enumerable.Range(0, Math.Max(r.Case.Queries.Count, r.Produced.Queries.Count)).Select(index => new
                {
                    ExpectedText = index < r.Case.Queries.Count ? r.Case.Queries[index].Text : null as string,
                    Text = index < r.Produced.Queries.Count ? r.Produced.Queries[index].Text : null,
                    ExpectedPeriod = index < r.Case.Queries.Count ? Period(r.Case.Queries[index].Period) : null,
                    Period = index < r.Produced.Queries.Count ? Period(r.Produced.Queries[index].Period) : null,
                    PeriodOk = index < r.Case.Queries.Count ? r.Metrics.Get<BooleanMetric>(Metrics.PeriodOk(index)).Value : null,
                    PeriodReason = index < r.Case.Queries.Count ? r.Metrics.Get<BooleanMetric>(Metrics.PeriodOk(index)).Reason : null,
                }),
            }),
            Totals = new
            {
                Cases = totals.Cases,
                QueryCountOk = totals.QueryCountOk,
                PeriodsOk = totals.PeriodsOk,
                Periods = totals.Periods,
                ElapsedSeconds = Math.Round(elapsed.TotalSeconds, 1),
            },
        };
        return (name, JsonSerializer.Serialize(record, Json));
    }

    private static object? Period(Period? period) => period is null ? null : new { period.From, period.To };
}

internal sealed record Totals(int Cases, int QueryCountOk, int PeriodsOk, int Periods);

internal static class Metrics
{
    public const string QueryCount = "query-count";

    public static string PeriodOk(int index) => $"period-ok-{index + 1}";
}
