using System.Text.RegularExpressions;

namespace Librarian.Evals.Search;

internal static partial class Text
{
    [GeneratedRegex(@"\s+")]
    private static partial Regex Whitespace();

    public static string Squeeze(string text) => Whitespace().Replace(text, "");

    public static bool Contains(string squeezedHaystack, string quote) => squeezedHaystack.Contains(Squeeze(quote));
}
