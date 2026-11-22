using System.Text.RegularExpressions;

namespace Application.Handlers.Store;

public static partial class Sections
{
    [GeneratedRegex(@"^#+\s+(.+)$")]
    private static partial Regex Heading();

    [GeneratedRegex(@"^!\[[^\]]*\]\([^)]*\)$")]
    private static partial Regex Image();

    public static List<(string Heading, string Text)> FromMarkdown(string markdown)
    {
        var sections = new List<(string Heading, string Text)>();
        var seen = new HashSet<string>();
        var heading = "";
        var lines = new List<string>();
        foreach (var line in markdown.Split('\n'))
        {
            var trimmed = line.Trim();
            var match = Heading().Match(trimmed);
            if (match.Success && !seen.Contains(match.Groups[1].Value.Trim()))
            {
                Flush(sections, heading, lines);
                heading = match.Groups[1].Value.Trim();
                seen.Add(heading);
                lines = [];
            }
            else if (!Image().Match(trimmed).Success)
            {
                lines.Add(line);
            }
        }
        Flush(sections, heading, lines);
        return sections;
    }

    private static void Flush(List<(string Heading, string Text)> sections, string heading, List<string> lines)
    {
        var text = string.Join("\n", lines).Trim();
        if (heading.Length > 0 || text.Length > 0)
            sections.Add((heading, text));
    }
}
