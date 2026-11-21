using System.Globalization;
using System.Text.RegularExpressions;

namespace Librarian.Application.Handlers.Ingest.Extract;

public static partial class FieldVerifier
{
    [GeneratedRegex(@"^\d{4}-\d{2}-\d{2}$")]
    private static partial Regex DatePattern();

    [GeneratedRegex(@"^-?\d+(\.\d+)?$")]
    private static partial Regex NumberPattern();

    public static bool FoundIn(string text, string? asWritten)
        => asWritten is not null && Flatten(text).Contains(Flatten(asWritten), StringComparison.Ordinal);

    public static bool WellFormed(FieldKind kind, string? value) => kind switch
    {
        FieldKind.Date => value is not null && DatePattern().IsMatch(value)
            && DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _),
        FieldKind.Number => value is not null && NumberPattern().IsMatch(value),
        _ => true,
    };

    public static VerifyReport Check(ExtractDraft draft, string text)
    {
        var checks = new List<FieldCheck>();
        checks.Add(ValidityCheck(draft.Validity, text));
        checks.AddRange(draft.Fields.Select(f => FieldCheckFor(f, text)));
        var problems = checks.Where(c => !c.Found || !c.WellFormed).ToList();
        var summary = problems.Count == 0
            ? "Every value is found in the text and well formed."
            : string.Join(" ", problems.Select(c => c.Message));
        return new VerifyReport(checks, summary);
    }

    private static FieldCheck ValidityCheck(ValidityDraft validity, string text)
    {
        var found = FoundIn(text, validity.AsWritten);
        var wellFormed = WellFormed(FieldKind.Date, validity.Start)
            && (string.IsNullOrEmpty(validity.End) || WellFormed(FieldKind.Date, validity.End));
        return new FieldCheck("validity", found, wellFormed, Problem("validity", validity.AsWritten, found, wellFormed));
    }

    private static FieldCheck FieldCheckFor(FieldDraft field, string text)
    {
        var found = FoundIn(text, field.AsWritten);
        var wellFormed = WellFormed(field.Kind, field.Value);
        return new FieldCheck(field.Name, found, wellFormed, Problem(field.Name, field.AsWritten, found, wellFormed, field.Value, field.Kind));
    }

    private static string Problem(string name, string asWritten, bool found, bool wellFormed, string? value = null, FieldKind kind = FieldKind.Text)
    {
        if (!found)
            return $"{name}: {asWritten} is not in the text; copy it exactly as written, or leave the field out.";
        if (!wellFormed)
            return $"{name}: {value} is not a well formed {kind.ToString().ToLowerInvariant()}; use YYYY-MM-DD for dates and a decimal with a dot (1234.56) for amounts.";
        return $"{name}: ok.";
    }

    private static string Flatten(string text) => string.Concat(text.Where(c => !char.IsWhiteSpace(c)));
}
