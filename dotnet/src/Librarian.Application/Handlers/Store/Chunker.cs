using System.Text.RegularExpressions;

namespace Librarian.Application.Handlers.Store;

public sealed partial class Chunker(int tokenBudget, Func<string, CancellationToken, Task<int>> countTokens)
{
    private static readonly string[] Splitters = ["(?<=[.?!]) ", "(?<=,) ", " "];

    private readonly Dictionary<string, int> _counts = [];

    public async Task<List<string>> ChunkAsync(string header, string text, CancellationToken cancellationToken)
    {
        var room = tokenBudget - await CountAsync(header, cancellationToken);
        if (room <= 0)
            throw new InvalidOperationException($"The chunk header alone is over the token budget ({tokenBudget}).");

        var pieces = new List<string>();
        foreach (var paragraph in text.Split("\n\n"))
        {
            if (paragraph.Trim().Length == 0)
                continue;
            pieces.AddRange(await FitAsync(paragraph, room, 0, cancellationToken));
        }

        var groups = new List<List<string>>();
        var current = new List<string>();
        var currentSize = 0;
        foreach (var piece in pieces)
        {
            var pieceSize = await CountAsync(piece, cancellationToken);
            if (current.Count > 0 && currentSize + pieceSize > room)
            {
                groups.Add(current);
                current = [];
                currentSize = 0;
            }
            current.Add(piece);
            currentSize += pieceSize;
        }
        if (current.Count > 0)
            groups.Add(current);

        return [.. groups.Select(group => $"{header}\n{string.Join(" ", group)}")];
    }

    private async Task<List<string>> FitAsync(string text, int room, int level, CancellationToken cancellationToken)
    {
        if (await CountAsync(text, cancellationToken) <= room)
            return [text];
        if (level == Splitters.Length)
            return [text];
        var pieces = new List<string>();
        foreach (var part in Regex.Split(text, Splitters[level]))
            pieces.AddRange(await FitAsync(part, room, level + 1, cancellationToken));
        return pieces;
    }

    private async Task<int> CountAsync(string text, CancellationToken cancellationToken)
    {
        if (text.Trim().Length == 0)
            return 0;
        if (_counts.TryGetValue(text, out var count))
            return count;
        count = await countTokens(text, cancellationToken);
        _counts[text] = count;
        return count;
    }
}
