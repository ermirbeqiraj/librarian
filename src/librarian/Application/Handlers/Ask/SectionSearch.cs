using System.Text.RegularExpressions;
using Application.Domain;
using Application.Ports.Retrieve;
using Microsoft.EntityFrameworkCore;

namespace Application.Handlers.Ask;

public sealed partial class SectionSearch(LibrarianDbContext db)
{
    public const int TrimLimit = 2000;
    public const string TrimMarker = "[…]";

    public async Task<List<object>> HitsAsync(
        IReadOnlyList<ChunkHit> chunks,
        string query,
        HashSet<long> seen,
        CancellationToken cancellationToken = default)
    {
        var best = new Dictionary<long, long>();
        var order = new List<long>();
        foreach (var hit in chunks.OrderBy(h => h.Rank))
        {
            if (best.ContainsKey(hit.SectionId))
                continue;
            best[hit.SectionId] = hit.ChunkId;
            order.Add(hit.SectionId);
        }
        var picked = order;
        var hits = new List<object>();

        var sections = await db.Set<Section>()
            .Where(s => picked.Contains(s.Id))
            .Select(s => new { s.Id, s.DocumentId, s.Heading, s.Text })
            .ToDictionaryAsync(s => s.Id, cancellationToken);
        var documentIds = sections.Values.Select(s => s.DocumentId).Distinct().ToList();
        var documents = await db.Documents
            .Where(d => documentIds.Contains(d.Id))
            .Select(d => new { d.Id, d.Kind, d.ValidityStart, d.ValidityEnd })
            .ToDictionaryAsync(d => d.Id, cancellationToken);
        var issuers = await db.Set<Field>()
            .Where(f => f.Name == "issuer" && documentIds.Contains(f.DocumentId))
            .Select(f => new { f.DocumentId, f.Value })
            .ToDictionaryAsync(f => f.DocumentId, cancellationToken);
        var chunkIds = picked.Where(sections.ContainsKey).Select(id => best[id]).ToList();
        var bestChunks = await db.Set<Chunk>()
            .Where(c => chunkIds.Contains(c.Id))
            .Select(c => new { c.Id, c.Text })
            .ToDictionaryAsync(c => c.Id, cancellationToken);

        foreach (var sectionId in picked)
        {
            if (seen.Contains(sectionId))
            {
                hits.Add(new AskedSeen(sectionId, AlreadyReturned: true));
                continue;
            }
            seen.Add(sectionId);
            if (!sections.TryGetValue(sectionId, out var section) || !documents.TryGetValue(section.DocumentId, out var document))
                continue;
            bestChunks.TryGetValue(best[sectionId], out var chunk);
            hits.Add(new AskedHit(
                sectionId,
                section.DocumentId,
                document.Kind,
                issuers.TryGetValue(section.DocumentId, out var issuer) ? issuer.Value : null,
                new Validity(document.ValidityStart, document.ValidityEnd),
                section.Heading,
                Trim(section.Text, chunk?.Text, query)));
        }
        return hits;
    }

    public static string Trim(string text, string? chunkText, string query)
    {
        if (text.Length <= TrimLimit)
            return text;
        return Window(text, Anchor(text, chunkText, query));
    }

    public static int Anchor(string text, string? chunkText, string query)
    {
        var earliest = -1;
        foreach (var term in WordPattern().Matches(query).Select(m => m.Value).Where(term => term.Length >= 3))
        {
            var match = Term(term).Match(text);
            if (match.Success && (earliest < 0 || match.Index < earliest))
                earliest = match.Index;
        }
        if (earliest >= 0)
            return earliest;
        var position = Locate(text, chunkText);
        if (position is not null)
            return position.Value;
        return text.Length / 2;
    }

    private static string Window(string text, int anchor)
    {
        var start = Math.Max(0, Math.Min(anchor - TrimLimit / 2, text.Length - TrimLimit));
        var end = start + TrimLimit;
        return (start > 0 ? TrimMarker : "") + text[start..end] + (end < text.Length ? TrimMarker : "");
    }

    [GeneratedRegex(@"\w+")]
    private static partial Regex WordPattern();

    private static Regex Term(string term)
    {
        var chars = term.ToLowerInvariant().Select(c => Accented.TryGetValue(c, out var group) ? group : c.ToString()).ToArray();
        return new Regex("\\b" + string.Join("", chars) + "\\b", RegexOptions.IgnoreCase);
    }

    private static int? Locate(string haystack, string? needle)
    {
        if (string.IsNullOrEmpty(needle))
            return null;
        var body = needle.Contains('\n') ? needle.Split('\n', 2)[1] : needle;
        var (squeezed, index) = Squeeze(haystack);
        var cut = Regex.Replace(body, @"\s+", " ").Trim();
        var position = cut.Length == 0 ? -1 : squeezed.Contains(cut) ? squeezed.IndexOf(cut, StringComparison.Ordinal) : -1;
        if (position < 0)
            return null;
        return index[Math.Min(position, index.Count - 1)];
    }

    private static (string Squeezed, List<int> Index) Squeeze(string text)
    {
        var chars = new List<char>();
        var index = new List<int>();
        var previousSpace = true;
        for (var position = 0; position < text.Length; position++)
        {
            var c = text[position];
            if (char.IsWhiteSpace(c))
            {
                if (!previousSpace && chars.Count > 0)
                {
                    chars.Add(' ');
                    index.Add(position);
                }
                previousSpace = true;
            }
            else
            {
                chars.Add(c);
                index.Add(position);
                previousSpace = false;
            }
        }
        return (new string([.. chars]), index);
    }

    private static readonly Dictionary<char, string> Accented = new()
    {
        ['a'] = "[aàáâãäåAÀÁÂÃÄÅ]",
        ['e'] = "[eèéêëEÈÉÊË]",
        ['i'] = "[iìíîïIÌÍÎÏ]",
        ['o'] = "[oòóôõöOÒÓÔÕÖ]",
        ['u'] = "[uùúûüUÙÚÛÜ]",
        ['c'] = "[cçCÇ]",
    };
}
