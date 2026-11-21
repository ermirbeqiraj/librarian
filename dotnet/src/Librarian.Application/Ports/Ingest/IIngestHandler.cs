namespace Librarian.Application.Ports.Ingest;

public interface IIngestHandler
{
    Task HandleAsync(IngestFile file, CancellationToken cancellationToken);
}

public sealed record IngestFile(string Path, string Name, long Size);
