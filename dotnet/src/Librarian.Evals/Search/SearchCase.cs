using System.Globalization;
using System.Text.Json;
using Librarian.Application.Ports.Retrieve;
using Librarian.Evals.Common;

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
            var from = Day(path, index, item.Period.From);
            var to = Day(path, index, item.Period.To);
            if (from > to)
                throw new InvalidDataException($"Case {index} in {path} has a period whose from {item.Period.From} is after to {item.Period.To}.");
            period = new Period(from, to);
        }
        return new SearchCase(Path.GetFileName(path), index, item.Query, item.From, item.Quotes, period, item.Author ?? "me", item.Note);
    }

    private static DateOnly? Day(string path, int index, string? value)
    {
        if (value is null)
            return null;
        if (DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var day))
            return day;
        throw new InvalidDataException($"Case {index} in {path} has a period date '{value}' that is not a real ISO day (yyyy-MM-dd).");
    }

    private sealed record RawCase(string? Query, string? From, List<string> Quotes, string? Author, string? Note, RawPeriod? Period);

    private sealed record RawPeriod(string? From, string? To);
}
