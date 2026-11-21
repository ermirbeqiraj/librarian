using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;

namespace Librarian.Adapters.FileSystem;

public sealed class IngestFileStore : IIngestFileStore
{
    private readonly LibrarianOptions _paths;

    public IngestFileStore(LibrarianOptions paths)
    {
        _paths = paths;
        Directory.CreateDirectory(paths.ResultsPath);
        Directory.CreateDirectory(paths.ProcessedPath);
    }

    public async Task WriteResultAsync(string fileName, string json, CancellationToken cancellationToken)
        => await File.WriteAllTextAsync(Path.Combine(_paths.ResultsPath, fileName + ".json"), json, cancellationToken);

    public Task MoveToProcessedAsync(string path, CancellationToken cancellationToken)
    {
        var destination = Path.Combine(_paths.ProcessedPath, Path.GetFileName(path));
        if (File.Exists(destination))
            File.Delete(path);
        else
            File.Move(path, destination);
        return Task.CompletedTask;
    }
}
