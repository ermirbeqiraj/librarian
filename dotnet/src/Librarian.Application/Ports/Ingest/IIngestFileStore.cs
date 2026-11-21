namespace Librarian.Application.Ports.Ingest;

public interface IIngestFileStore
{
    Task MoveToProcessedAsync(string path, CancellationToken cancellationToken);
    Task DeleteAsync(string path, CancellationToken cancellationToken);
}
