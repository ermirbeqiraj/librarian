using System.Text.Json;
using Application.Handlers.Ask;
using Evals.Common;

namespace Evals.Retrieval;

internal static class RunRecord
{
    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static (string Name, string Record) Build(
        AskOptions options,
        List<(RetrieveCase Case, AskResult? Result, Marks? Marks, string? Error)> results,
        Dictionary<string, List<string>> spans,
        TimeSpan elapsed)
    {
        var name = $"run-{DateTime.Now:yyyy-MM-ddTHH-mm-ss}-retrieval.json";
        var scored = results.Where(r => r.Marks is not null).ToList();
        var answered = scored.Where(r => r.Marks!.Answer is not null).ToList();
        var record = new
        {
            RanAt = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            Commit = Git.FindSha(),
            Model = options.Model,
            Reasoning = options.ReasoningEffort,
            Prompt = Path.GetFileName(options.InstructionsPath),
            Cases = results.Select(r => new
            {
                File = r.Case.FileName,
                Index = r.Case.Index,
                Question = r.Case.Question,
                Type = r.Case.Type,
                Note = r.Case.Note,
                Expected = new
                {
                    Value = r.Case.AnswerValue,
                    Unit = r.Case.Unit,
                    Quotes = r.Case.Quotes,
                    Status = r.Case.ExpectedStatus,
                },
                Status = r.Result is null ? null : AskHandler.Wire(r.Result.Status),
                Marks = r.Marks is null ? null : new
                {
                    Hit = r.Marks.Hit,
                    Answer = r.Marks.Answer,
                    Honesty = r.Marks.Honesty,
                },
                Result = r.Result,
                Error = r.Error,
                Spans = (r.Result is not null && spans.TryGetValue(r.Result.Id, out var own)
                    ? own.Select(Parse) : []).ToList(),
            }),
            Totals = new
            {
                Cases = results.Count,
                Scored = scored.Count,
                Hit = scored.Count(r => r.Marks!.Hit),
                Answer = answered.Count(r => r.Marks!.Answer is true),
                Answered = answered.Count,
                Honesty = scored.Count(r => r.Marks!.Honesty),
                Skipped = results.Count - scored.Count,
                ElapsedSeconds = Math.Round(elapsed.TotalSeconds, 1),
            },
        };
        return (name, JsonSerializer.Serialize(record, Json));
    }

    private static object Parse(string span) => JsonDocument.Parse(span).RootElement;
}
