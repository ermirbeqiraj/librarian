using System.Globalization;
using System.Text.RegularExpressions;

namespace Librarian.Application.Ports.Retrieve;

public enum PeriodOp
{
    During,
    After,
    Before,
    On
}

public sealed record Period
{
    private static readonly Regex ValuePattern = new(@"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$", RegexOptions.Compiled);

    private Period(PeriodOp op, string value, DateOnly start, DateOnly dayAfter)
    {
        Op = op;
        Value = value;
        Start = start;
        DayAfter = dayAfter;
    }

    public PeriodOp Op { get; }
    public string Value { get; }
    public DateOnly Start { get; }
    public DateOnly DayAfter { get; }

    public static Period Create(PeriodOp op, string value)
    {
        var trimmed = value.Trim();
        var match = ValuePattern.Match(trimmed);
        if (!match.Success)
            throw new ArgumentException($"period value must be a year, month or day (YYYY[-MM[-DD]]): '{value}'", nameof(value));
        var year = match.Groups[1].Value;
        var month = match.Groups[2].Value;
        var day = match.Groups[3].Value;
        DateOnly start;
        if (day.Length > 0)
        {
            if (!DateOnly.TryParseExact($"{year}-{month}-{day}", "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out start))
                throw new ArgumentException($"period value is not a real day: '{value}'", nameof(value));
        }
        else if (month.Length > 0)
        {
            if (!DateOnly.TryParseExact($"{year}-{month}-01", "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out start))
                throw new ArgumentException($"period value is not a real month: '{value}'", nameof(value));
        }
        else
        {
            start = new DateOnly(int.Parse(year, CultureInfo.InvariantCulture), 1, 1);
        }
        var dayAfter = day.Length > 0 ? start.AddDays(1)
            : month.Length > 0 ? start.AddMonths(1)
            : start.AddYears(1);
        return new Period(op, trimmed, start, dayAfter);
    }
}
