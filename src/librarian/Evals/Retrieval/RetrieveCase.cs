using System.Text.Json;
using Evals.Common;

namespace Evals.Retrieval;

internal sealed record RetrieveCase(
    string FileName,
    int Index,
    string Question,
    string Type,
    JsonElement? AnswerValue,
    string? Unit,
    IReadOnlyList<string> Quotes,
    string ExpectedStatus,
    string? Note)
{
    public bool ExpectsAnswer => AnswerValue is not null || Quotes.Count > 0;

    public static List<RetrieveCase> Load(string folder, string? file)
    {
        if (!Directory.Exists(folder))
            throw new InvalidOperationException($"The retrieval cases folder is missing: {folder}");
        List<string> paths = file is null
            ? [.. Directory.EnumerateFiles(folder, "*.json").Order()]
            : [Path.Combine(folder, file)];
        if (paths.Count == 0 || !File.Exists(paths[0]))
            throw new InvalidOperationException(file is null
                ? $"No case files in {folder}."
                : $"No case file {file} in {folder}.");
        var cases = new List<RetrieveCase>();
        foreach (var path in paths)
        {
            var raw = JsonSerializer.Deserialize<List<RawCase>>(File.ReadAllText(path), Json.Options)
                ?? throw new InvalidOperationException($"Unreadable case file: {path}");
            var index = 0;
            foreach (var item in raw)
                cases.Add(Parse(path, index++, item));
        }
        return cases;
    }

    private static RetrieveCase Parse(string path, int index, RawCase item)
    {
        if (string.IsNullOrWhiteSpace(item.Question))
            throw new InvalidDataException($"Case {index} in {path} has no question.");
        if (item.Answer is null)
            throw new InvalidDataException($"Case {index} in {path} has no answer.");
        JsonElement? value = null;
        if (item.Answer.Value.TryGetProperty("value", out var element) && element.ValueKind is not JsonValueKind.Null)
            value = element;
        List<string> quotes = [];
        if (item.Answer.Value.TryGetProperty("quote", out var quote))
            quotes.AddRange(quote.ValueKind == JsonValueKind.Array
                ? quote.EnumerateArray().Select(q => q.GetString() ?? throw Bad(path, index, "a quote is not text"))
                : [quote.GetString() ?? throw Bad(path, index, "the quote is not text")]);
        var status = "found";
        if (item.Answer.Value.TryGetProperty("status", out var statusElement))
        {
            status = statusElement.GetString() ?? throw Bad(path, index, "the status is not text");
            if (status is not ("found" or "partial" or "not_found"))
                throw Bad(path, index, $"the status '{status}' is not one of found, partial, not_found");
        }
        if (value is null && quotes.Count == 0 && status == "found")
            throw Bad(path, index, "the answer has no value, no quote and no status");
        return new RetrieveCase(
            Path.GetFileName(path),
            index,
            item.Question,
            item.Type ?? "question",
            value,
            item.Answer.Value.TryGetProperty("unit", out var unit) && unit.ValueKind is JsonValueKind.String ? unit.GetString() : null,
            quotes,
            status,
            item.Note);

        static InvalidDataException Bad(string path, int index, string why) => new($"Case {index} in {path}: {why}.");
    }

    private sealed record RawCase(string? Question, string? Type, JsonElement? Answer, string? Note);
}
