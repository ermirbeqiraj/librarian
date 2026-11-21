namespace Librarian.Application.Ports.Ingest;

public interface IIngestFileStore
{
    Task WriteResultAsync(string fileName, string json, CancellationToken cancellationToken);
    Task MoveToProcessedAsync(string path, CancellationToken cancellationToken);
}
