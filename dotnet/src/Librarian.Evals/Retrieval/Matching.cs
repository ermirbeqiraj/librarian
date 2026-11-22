using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Librarian.Application.Handlers.Ask;

namespace Librarian.Evals.Retrieval;

internal partial class Matching
{
    private static readonly Dictionary<string, (string Base, decimal Factor)> Units = new()
    {
        ["€"] = ("EUR", 1m),
        ["eur"] = ("EUR", 1m),
        ["euro"] = ("EUR", 1m),
        ["mc"] = ("mc", 1m),
        ["m3"] = ("mc", 1m),
        ["m³"] = ("mc", 1m),
        ["l"] = ("mc", 0.001m),
        ["lt"] = ("mc", 0.001m),
        ["litri"] = ("mc", 0.001m),
        ["litro"] = ("mc", 0.001m),
        ["smc"] = ("Smc", 1m),
        ["kwh"] = ("kWh", 1m),
    };

    public static bool ContainsQuote(string quote, List<AskedPassage> passages)
    {
        var wanted = Squeeze(quote);
        return passages.Any(passage => Squeeze(passage.Text).Contains(wanted, StringComparison.Ordinal));
    }

    public static bool AnySameValue(JsonElement expected, string? unit, List<AskedValue> values)
        => values.Any(value => SameValue(expected, unit, value));

    private static bool SameValue(JsonElement expected, string? unit, AskedValue got)
    {
        if (expected.ValueKind is JsonValueKind.String)
            return SameText(expected.GetString()!, got.Value);
        var amount = ParseAmount(got);
        if (amount is null)
            return false;
        var (numbers, gotUnit) = amount.Value;
        return numbers.Any(number => SameAmount(expected.GetDecimal(), unit, number, gotUnit));
    }

    private static bool SameAmount(decimal expected, string? unit, decimal number, string? gotUnit)
    {
        // A bare number is taken in the expected unit: 63.33 = 63.33 EUR.
        if (unit is null || gotUnit is null)
            return number == expected;
        if (!Units.TryGetValue(unit.ToLowerInvariant(), out var wanted))
            return false;
        if (!Units.TryGetValue(gotUnit.ToLowerInvariant(), out var had))
            return false;
        return wanted.Base == had.Base && number * had.Factor == expected * wanted.Factor;
    }

    private static (List<decimal> Numbers, string? Unit)? ParseAmount(AskedValue value)
    {
        if (value.Value.ValueKind is JsonValueKind.Number)
            return ([value.Value.GetDecimal()], value.Unit);
        var text = value.Value.GetString()!.Trim();
        var match = Amount().Match(text);
        if (!match.Success)
            return null;
        var numbers = ParseNumbers(match.Groups[2].Value);
        if (numbers.Count == 0)
            return null;
        var unit = match.Groups[1].Value.Length > 0
            ? match.Groups[1].Value
            : match.Groups[3].Value.Length > 0 ? match.Groups[3].Value : value.Unit;
        return (numbers, unit);
    }

    internal static List<decimal> ParseNumbers(string text)
    {
        var readings = new List<string>();
        var comma = text.Contains(',');
        var dot = text.Contains('.');
        if (comma && dot)
        {
            readings.Add(text.LastIndexOf(',') > text.LastIndexOf('.')
                ? text.Replace(".", "").Replace(",", ".")
                : text.Replace(",", ""));
        }
        else if (comma)
            readings.Add(text.Replace(',', '.'));
        else if (text.Count(c => c == '.') > 1)
            readings.Add(text.Replace(".", ""));
        else if (ThreeDigits().IsMatch(text))
        {
            readings.Add(text.Replace(".", ""));
            readings.Add(text);
        }
        else
            readings.Add(text);
        var numbers = new List<decimal>();
        foreach (var reading in readings)
        {
            if (decimal.TryParse(reading, NumberStyles.Number, CultureInfo.InvariantCulture, out var number))
                numbers.Add(number);
        }
        return numbers;
    }

    private static bool SameText(string expected, JsonElement got)
    {
        var text = got.ValueKind is JsonValueKind.Number ? got.GetDecimal().ToString(CultureInfo.InvariantCulture) : got.GetString()!;
        if (TryDate(expected, out var expectedDate))
            return TryDate(text, out var date) && date == expectedDate;
        return Squeeze(expected).Equals(Squeeze(text), StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryDate(string text, out DateOnly date)
        => DateOnly.TryParseExact(text.Trim(), "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out date);

    internal static string Squeeze(string text)
        => Whitespace().Replace(text, "");

    [GeneratedRegex(@"(€)?\s*(-?[\d.,]+)\s*(\S*)")]
    private static partial Regex Amount();

    [GeneratedRegex(@"^-?\d{1,3}\.\d{3}$")]
    private static partial Regex ThreeDigits();

    [GeneratedRegex(@"\s+")]
    private static partial Regex Whitespace();
}
