using System.Globalization;
using System.Text.Json;
using Librarian.Application.Ports.Retrieve;
using Librarian.Evals.Common;

namespace Librarian.Evals.Refine;

internal sealed record RefineCase(
    string FileName,
    int Index,
    string Question,
    DateOnly Today,
    IReadOnlyList<ExpectedQuery> Queries,
    string Author,
    string? Note)
{
    public static List<RefineCase> Load(string folder)
    {
        if (!Directory.Exists(folder))
            throw new InvalidOperationException($"The refine cases folder is missing: {folder}");
        var cases = new List<RefineCase>();
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

    private static RefineCase Parse(string path, int index, RawCase item)
    {
        if (string.IsNullOrWhiteSpace(item.Question))
            throw new InvalidDataException($"Case {index} in {path} has no question.");
        if (!DateOnly.TryParseExact(item.Today, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var today))
            throw new InvalidDataException($"Case {index} in {path} has a today '{item.Today}' that is not a real ISO day (yyyy-MM-dd).");
        if (item.Queries is not { Count: > 0 })
            throw new InvalidDataException($"Case {index} in {path} has no queries.");
        var queries = new List<ExpectedQuery>();
        var position = 0;
        foreach (var query in item.Queries)
        {
            if (string.IsNullOrWhiteSpace(query.Text))
                throw new InvalidDataException($"Case {index} in {path} has query {position} without a text.");
            Period? period = null;
            if (query.Period is not null)
            {
                var from = Day(path, index, position, query.Period.From);
                var to = Day(path, index, position, query.Period.To);
                if (from > to)
                    throw new InvalidDataException($"Case {index} in {path} has query {position} with a period whose from is after to.");
                period = new Period(from, to);
            }
            queries.Add(new ExpectedQuery(query.Text, period));
            position++;
        }
        return new RefineCase(Path.GetFileName(path), index, item.Question, today, queries, item.Author ?? "me", item.Note);
    }

    private static DateOnly? Day(string path, int index, int position, string? value)
    {
        if (value is null)
            return null;
        if (DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var day))
            return day;
        throw new InvalidDataException($"Case {index} in {path} has query {position} with a period date '{value}' that is not a real ISO day (yyyy-MM-dd).");
    }

    private sealed record RawCase(string? Question, string? Today, List<RawQuery> Queries, string? Author, string? Note);

    private sealed record RawQuery(string? Text, RawPeriod? Period);

    private sealed record RawPeriod(string? From, string? To);
}

internal sealed record ExpectedQuery(string Text, Period? Period);
