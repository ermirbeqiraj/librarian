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

        var pieces = new List<Piece>();
        foreach (var block in text.Split("\n\n"))
        {
            if (block.Trim().Length == 0)
                continue;
            pieces.AddRange(await FitBlockAsync(block, room, cancellationToken));
        }

        var chunks = new List<string>();
        var current = new List<Piece>();
        var currentSize = 0;
        foreach (var piece in pieces)
        {
            var pieceSize = await CountAsync(piece.Text, cancellationToken);
            if (current.Count > 0 && currentSize + pieceSize > room)
            {
                chunks.Add(Join(header, current));
                current = [];
                currentSize = 0;
            }
            current.Add(piece);
            currentSize += pieceSize;
        }
        if (current.Count > 0)
            chunks.Add(Join(header, current));

        return chunks;
    }

    private async Task<List<Piece>> FitBlockAsync(string block, int room, CancellationToken cancellationToken)
    {
        if (await CountAsync(block, cancellationToken) <= room)
            return [new Piece(block, false)];
        if (IsTable(block))
            return await SplitTableAsync(block, room, cancellationToken);
        var pieces = new List<Piece>();
        foreach (var part in await FitAsync(block, room, 0, cancellationToken))
            pieces.Add(new Piece(part, false));
        return pieces;
    }

    private async Task<List<Piece>> SplitTableAsync(string table, int room, CancellationToken cancellationToken)
    {
        var lines = table.Split('\n');
        var header = string.Join("\n", lines.Take(2));
        var headerSize = await CountAsync(header, cancellationToken);
        var pieces = new List<Piece>();
        var rows = new List<string>();
        var rowsSize = 0;
        foreach (var row in lines.Skip(2))
        {
            var rowSize = await CountAsync(row, cancellationToken);
            if (rows.Count > 0 && headerSize + rowsSize + rowSize > room)
            {
                pieces.Add(new Piece($"{header}\n{string.Join("\n", rows)}", true));
                rows = [];
                rowsSize = 0;
            }
            if (headerSize + rowSize > room)
            {
                foreach (var part in await FitAsync(row, room - headerSize, 0, cancellationToken))
                    pieces.Add(new Piece($"{header}\n{part}", true));
                continue;
            }
            rows.Add(row);
            rowsSize += rowSize;
        }
        if (rows.Count > 0)
            pieces.Add(new Piece($"{header}\n{string.Join("\n", rows)}", true));
        return pieces;
    }

    private static bool IsTable(string block)
    {
        var lines = block.Split('\n');
        return lines.Length >= 2
            && lines[0].TrimStart().StartsWith('|')
            && lines[1].Contains("---");
    }

    private static string Join(string header, List<Piece> pieces)
        => $"{header}\n{string.Join("", pieces.Select((p, i) => (i > 0 && p.IsBlock ? "\n" : i > 0 ? " " : "") + p.Text))}";

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

    private sealed record Piece(string Text, bool IsBlock);
}
