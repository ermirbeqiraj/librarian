using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;
using Librarian.Ingest;
using Microsoft.Extensions.Logging.Abstractions;

namespace Librarian.Tests.Ingest;

public sealed class WorkerTests
{
    private sealed class RecordingHandler : IIngestHandler
    {
        public List<IngestFile> Files { get; } = [];

        public Task HandleAsync(IngestFile file, CancellationToken cancellationToken)
        {
            Files.Add(file);
            return Task.CompletedTask;
        }
    }

    [Fact]
    public async Task A_file_unchanged_for_60_seconds_reaches_the_handler()
    {
        var root = Path.Combine(Path.GetTempPath(), "librarian-worker-test-" + Guid.NewGuid().ToString("N"));
        var paths = new LibrarianOptions
        {
            Root = root,
            ScanIntervalSeconds = 1,
            Folders = new LibrarianOptions.FoldersOptions
            {
                Inbox = "inbox", Processed = "processed", Results = "results", Documents = "documents",
            },
        };
        paths.Validate();
        Directory.CreateDirectory(paths.InboxPath);

        var file = Path.Combine(paths.InboxPath, "invoice__1.pdf");
        await File.WriteAllBytesAsync(file, [1, 2, 3, 4], TestContext.Current.CancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));

        var handler = new RecordingHandler();
        var worker = new Worker(NullLogger<Worker>.Instance, paths, handler);
        await worker.StartAsync(TestContext.Current.CancellationToken);
        try
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(15);
            while (handler.Files.Count == 0 && DateTime.UtcNow < deadline)
                await Task.Delay(200, TestContext.Current.CancellationToken);
        }
        finally
        {
            await worker.StopAsync(TestContext.Current.CancellationToken);
        }

        var taken = Assert.Single(handler.Files);
        Assert.Equal("invoice__1.pdf", taken.Name);
        Assert.Equal(4, taken.Size);
        Assert.Equal(file, taken.Path);
        Directory.Delete(root, recursive: true);
    }

    [Fact]
    public async Task A_file_still_changing_is_not_taken()
    {
        var root = Path.Combine(Path.GetTempPath(), "librarian-worker-test-" + Guid.NewGuid().ToString("N"));
        var paths = new LibrarianOptions
        {
            Root = root,
            ScanIntervalSeconds = 1,
            Folders = new LibrarianOptions.FoldersOptions
            {
                Inbox = "inbox", Processed = "processed", Results = "results", Documents = "documents",
            },
        };
        paths.Validate();
        Directory.CreateDirectory(paths.InboxPath);

        var file = Path.Combine(paths.InboxPath, "invoice__2.pdf");
        await File.WriteAllBytesAsync(file, [1, 2, 3], TestContext.Current.CancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));

        var handler = new RecordingHandler();
        var worker = new Worker(NullLogger<Worker>.Instance, paths, handler);
        await worker.StartAsync(TestContext.Current.CancellationToken);
        try
        {

            for (var i = 0; i < 6; i++)
            {
                await File.AppendAllTextAsync(file, "x", TestContext.Current.CancellationToken);
                File.SetLastWriteTimeUtc(file, DateTime.UtcNow);
                await Task.Delay(700, TestContext.Current.CancellationToken);
            }
            Assert.Empty(handler.Files);
        }
        finally
        {
            await worker.StopAsync(TestContext.Current.CancellationToken);
            Directory.Delete(root, recursive: true);
        }
    }
}

public sealed class WorkerSurvivesTest
{
    private sealed class ViolentHandler : IIngestHandler
    {
        public int Calls { get; private set; }

        public Task HandleAsync(IngestFile file, CancellationToken cancellationToken)
        {
            Calls++;
            throw new IOException("the file opened a portal");
        }
    }

    [Fact]
    public async Task A_violently_failing_handler_does_not_kill_the_worker()
    {
        var root = Path.Combine(Path.GetTempPath(), "librarian-worker-test-" + Guid.NewGuid().ToString("N"));
        var librarianOptions = new LibrarianOptions
        {
            Root = root,
            ScanIntervalSeconds = 1,
            Folders = new LibrarianOptions.FoldersOptions
            {
                Inbox = "inbox", Processed = "processed", Results = "results", Documents = "documents",
            },
        };
        librarianOptions.Validate();
        Directory.CreateDirectory(librarianOptions.InboxPath);

        var file = Path.Combine(librarianOptions.InboxPath, "invoice__3.pdf");
        await File.WriteAllBytesAsync(file, [1], TestContext.Current.CancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));

        var handler = new ViolentHandler();
        var worker = new Worker(NullLogger<Worker>.Instance, librarianOptions, handler);
        await worker.StartAsync(TestContext.Current.CancellationToken);
        try
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(20);
            while (handler.Calls < 2 && DateTime.UtcNow < deadline)
            {
                await Task.Delay(200, TestContext.Current.CancellationToken);
            }
        }
        finally
        {
            await worker.StopAsync(TestContext.Current.CancellationToken);
        }

        Assert.True(handler.Calls >= 2);
        Directory.Delete(root, recursive: true);
    }
}
