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
        Directory.CreateDirectory(paths.QuarantinePath);
    }

    public Task MoveToProcessedAsync(string path, string relativeDestination, CancellationToken cancellationToken)
        => MoveAsync(_paths.ProcessedPath, path, relativeDestination);

    public Task MoveToQuarantineAsync(string path, string relativeDestination, CancellationToken cancellationToken)
        => MoveAsync(_paths.QuarantinePath, path, relativeDestination);

    private static Task MoveAsync(string root, string path, string relativeDestination)
    {
        var destination = Path.Combine(root, relativeDestination);
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
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
