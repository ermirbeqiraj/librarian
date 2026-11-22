using System.Text.Json;
using Librarian.Evals.Common;
using Microsoft.Extensions.AI.Evaluation;

namespace Librarian.Evals.Search;

internal static class RunRecord
{
    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static (string Name, string Json) Build(
        string mode, int limit, string embedder, int documents, int sections, int chunks,
        List<(SearchCase Case, EvaluationResult Metrics)> results,
        List<SearchCase> skipped,
        List<(string File, int Index, string Quote)> notes,
        Totals totals, TimeSpan elapsed)
    {
        var name = $"run-{DateTime.Now:yyyy-MM-ddTHH-mm-ss}-{mode}.json";
        var record = new
        {
            RanAt = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            Commit = Git.FindSha(),
            Mode = mode,
            Limit = limit,
            Embedder = embedder,
            Library = new { Documents = documents, Sections = sections, Chunks = chunks },
            Cases = results.Select(r => new
            {
                File = r.Case.FileName,
                Index = r.Case.Index,
                Author = r.Case.Author,
                Query = r.Case.Query,
                From = r.Case.From,
                ChunkRank = r.Metrics.Get<NumericMetric>(Metrics.ChunkRank).Value,
                SectionRank = r.Metrics.Get<NumericMetric>(Metrics.SectionRank).Value,
                OneChunk = r.Metrics.Get<BooleanMetric>(Metrics.OneChunk).Value,
                ChunkReason = r.Metrics.Get<NumericMetric>(Metrics.ChunkRank).Reason,
                SectionReason = r.Metrics.Get<NumericMetric>(Metrics.SectionRank).Reason,
                OneChunkReason = r.Metrics.Get<BooleanMetric>(Metrics.OneChunk).Reason,
            }),
            Skipped = skipped.Select(s => new { File = s.FileName, Index = s.Index, Query = s.Query, From = s.From }),
            Notes = notes.Select(n => new { File = n.File, Index = n.Index, Quote = n.Quote }),
            Totals = new
            {
                Runnable = totals.Count,
                SectionTop1 = totals.SectionTop1,
                SectionTop5 = totals.SectionTop5,
                ChunkTop1 = totals.ChunkTop1,
                ChunkTop5 = totals.ChunkTop5,
                OneChunk = totals.OneChunk,
                ElapsedSeconds = Math.Round(elapsed.TotalSeconds, 1),
            },
        };
        return (name, JsonSerializer.Serialize(record, Json));
    }
}

internal sealed record Totals(
    int SectionTop1, int SectionTop5, int ChunkTop1, int ChunkTop5, int OneChunk, int Count);

internal static class Metrics
{
    public const string ChunkRank = "chunk-rank";
    public const string SectionRank = "section-rank";
    public const string OneChunk = "one-chunk";
}

