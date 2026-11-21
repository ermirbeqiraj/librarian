namespace Librarian.Application.Ports.Ingest;

public interface IDocumentReader
{
    Task<IReadOnlyList<Page>> ReadAsync(string path, CancellationToken cancellationToken);
}

public sealed record Page(int Number, string Markdown);
