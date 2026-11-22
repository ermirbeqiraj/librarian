using Application.Handlers.Ingest;
using Application.Ports.Ingest;

namespace Adapters.FileSystem;

public sealed class IngestFileStore : IIngestFileStore
{
    private readonly LibrarianOptions _paths;

    public IngestFileStore(LibrarianOptions paths)
    {
        _paths = paths;
        Directory.CreateDirectory(paths.ResultsPath);
        Directory.CreateDirectory(paths.ProcessedPath);
    }

    public Task MoveToProcessedAsync(string path, CancellationToken cancellationToken)
    {
        var destination = Path.Combine(_paths.ProcessedPath, Path.GetFileName(path));
        if (File.Exists(destination))
            File.Delete(path);
        else
            File.Move(path, destination);
        return Task.CompletedTask;
    }

    public Task DeleteAsync(string path, CancellationToken cancellationToken)
    {
        File.Delete(path);
        return Task.CompletedTask;
    }
}
