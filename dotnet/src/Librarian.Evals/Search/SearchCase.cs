using System.Text.Json;
using Librarian.Application.Ports.Retrieve;

namespace Librarian.Evals.Search;

internal sealed record SearchCase(
    string FileName,
    int Index,
    string Query,
    string? From,
    IReadOnlyList<string> Quotes,
    Period? Period,
    string Author,
    string? Note)
{
    public static List<SearchCase> Load(string folder)
    {
        if (!Directory.Exists(folder))
            throw new InvalidOperationException($"The search cases folder is missing: {folder}");
        var cases = new List<SearchCase>();
        foreach (var path in Directory.EnumerateFiles(folder, "*.json").Order())
        {
            var raw = JsonSerializer.Deserialize<List<RawCase>>(File.ReadAllText(path), Json.Options)
                ?? throw new InvalidOperationException($"Unreadable case file: {path}");
            var index = 0;
            foreach (var item in raw)
            {
                cases.Add(Parse(path, index, item));
                index++;
            }
        }
        return cases;
    }

    private static SearchCase Parse(string path, int index, RawCase item)
    {
        if (string.IsNullOrWhiteSpace(item.Query)
            || string.IsNullOrWhiteSpace(item.From))
            throw new InvalidDataException($"Case {index} in {path} needs a query (rewriter output) and from (the original question).");
        if (item.Quotes is not { Count: > 0 })
            throw new InvalidDataException($"Case {index} in {path} has no quotes.");
        Period? period = null;
        if (item.Period is not null)
        {
            if (!Enum.TryParse<PeriodOp>(item.Period.Op, ignoreCase: true, out var op))
                throw new InvalidDataException($"Case {index} in {path} has an unknown period op '{item.Period.Op}'.");
            period = Period.Create(op, item.Period.Value);
        }
        return new SearchCase(Path.GetFileName(path), index, item.Query, item.From, item.Quotes, period, item.Author ?? "me", item.Note);
    }

    private sealed record RawCase(string? Query, string? From, List<string> Quotes, string? Author, string? Note, RawPeriod? Period);

    private sealed record RawPeriod(string Op, string Value);
}

internal static class Json
{
    public static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };
}
