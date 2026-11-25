namespace Application.Ports.Ingest;

public interface IIngestFileStore
{
    Task MoveToProcessedAsync(string path, string relativeDestination, CancellationToken cancellationToken);
    Task MoveToQuarantineAsync(string path, string relativeDestination, CancellationToken cancellationToken);
    Task DeleteAsync(string path, CancellationToken cancellationToken);
}
