using Adapters;
using Application.Domain;
using Application.Handlers.Ingest;
using Application.Ports.Ingest;
using Ingest;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;

namespace PostgresTests.Ingest;

[Collection("Postgres")]
public sealed class WorkerTests
{
    private sealed class ThrowingReader : IDocumentReader
    {
        public Task<IReadOnlyList<Page>> ReadAsync(string path, CancellationToken cancellationToken)
            => throw new IOException("no reader in tests");
    }

    private sealed class RefusingBudget : IOcrBudget
    {
        public bool TrySpend(out string refusal)
        {
            refusal = "the test budget refuses";
            return false;
        }
    }

    private sealed class Fixture : IAsyncDisposable
    {
        public ServiceProvider Provider { get; }
        public LibrarianOptions Paths { get; }
        public IngestOptions Ingest { get; }

        public Fixture()
        {
            var root = Path.Combine(Path.GetTempPath(), "librarian-worker-test-" + Guid.NewGuid().ToString("N"));
            Paths = new LibrarianOptions
            {
                Root = root,
                ScanIntervalSeconds = 1,
                Folders = new LibrarianOptions.FoldersOptions
                {
                    Inbox = "inbox", Processed = "processed", Results = "results", Documents = "documents",
                },
            };
            Paths.Validate();
            Directory.CreateDirectory(Paths.InboxPath);

            var config = new ConfigurationBuilder()
                .SetBasePath(Path.Combine(SolutionRoot.Find(), "librarian", "Ingest"))
                .AddJsonFile("appsettings.json", optional: false)
                .AddJsonFile("appsettings.Development.json", optional: true)
                .AddEnvironmentVariables()
                .Build();
            Ingest = config.GetSection("Ingest").Get<IngestOptions>() ?? new IngestOptions();
            var mistral = config.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();
            var connectionString = config.GetConnectionString("Postgres")
                ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");

            var services = new ServiceCollection();
            services.AddLogging();
            services.AddLibrarianAdapters(Paths, Ingest, mistral);
            services.AddKeyedSingleton<IDocumentReader, ThrowingReader>("doclingReader");
            services.AddKeyedSingleton<IDocumentReader, ThrowingReader>("ocrReader");
            services.AddSingleton<IOcrBudget, RefusingBudget>();
            services.AddPostgres(connectionString);
            services.AddIngestHandler();
            Provider = services.BuildServiceProvider();
        }

        public async Task<Ingestion?> RowAsync(string fileName, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            return await db.Ingestions.OrderByDescending(i => i.Id).FirstOrDefaultAsync(i => i.FileName == fileName, cancellationToken);
        }

        public async Task<int> AttemptsAsync(string fileName, long size, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            return await db.Ingestions.CountAsync(i => i.FileName == fileName && i.FileSize == size, cancellationToken);
        }

        public async Task AddBankedRowsAsync(string fileName, long size, int count, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            for (var i = 0; i < count; i++)
            {
                var ingestion = Ingestion.Create(fileName, size);
                db.Ingestions.Add(ingestion);
                await db.SaveChangesAsync(cancellationToken);
                ingestion.MarkError(IngestionErrorReason.ReadFailed, "banked by the test");
                await db.SaveChangesAsync(cancellationToken);
            }
        }

        public async Task RemoveRowsAsync(string fileName, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            db.Ingestions.RemoveRange(db.Ingestions.Where(i => i.FileName == fileName));
            await db.SaveChangesAsync(cancellationToken);
        }

        public Worker NewWorker()
            => new(NullLogger<Worker>.Instance, Paths, Ingest,
                Provider.GetRequiredService<IIngestFileStore>(), Provider.GetRequiredService<IServiceScopeFactory>());

        public async ValueTask DisposeAsync()
        {
            await Provider.DisposeAsync();
            if (Directory.Exists(Paths.Root))
                Directory.Delete(Paths.Root, recursive: true);
        }
    }

    private static async Task RunUntil(Fixture fixture, Func<Task<bool>> until, CancellationToken cancellationToken)
    {
        var worker = fixture.NewWorker();
        await worker.StartAsync(cancellationToken);
        try
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(20);
            while (!await until() && DateTime.UtcNow < deadline)
                await Task.Delay(200, cancellationToken);
        }
        finally
        {
            await worker.StopAsync(cancellationToken);
        }
    }

    [Fact]
    public async Task A_file_unchanged_for_60_seconds_is_taken_and_its_failure_is_banked()
    {
        await using var fixture = new Fixture();
        var cancellationToken = TestContext.Current.CancellationToken;
        var name = "test__taken_" + Guid.NewGuid().ToString("N")[..8] + ".pdf";
        var file = Path.Combine(fixture.Paths.InboxPath, name);
        await File.WriteAllBytesAsync(file, [1, 2, 3, 4], cancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));

        await RunUntil(fixture, async () => await fixture.RowAsync(name, cancellationToken) is not null, cancellationToken);

        var row = await fixture.RowAsync(name, cancellationToken);
        Assert.NotNull(row);
        Assert.Equal(IngestionState.Error, row!.State);
        Assert.Equal(IngestionErrorReason.ReadFailed, row.ErrorReason);
        Assert.False(File.Exists(file));
        Assert.True(File.Exists(Path.Combine(fixture.Paths.ProcessedPath, name)));
        await fixture.RemoveRowsAsync(name, cancellationToken);
    }

    [Fact]
    public async Task A_file_still_changing_is_not_taken()
    {
        await using var fixture = new Fixture();
        var cancellationToken = TestContext.Current.CancellationToken;
        var name = "test__changing_" + Guid.NewGuid().ToString("N")[..8] + ".pdf";
        var file = Path.Combine(fixture.Paths.InboxPath, name);
        await File.WriteAllBytesAsync(file, [1, 2, 3], cancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));

        var worker = fixture.NewWorker();
        await worker.StartAsync(cancellationToken);
        try
        {
            for (var i = 0; i < 6; i++)
            {
                await File.AppendAllTextAsync(file, "x", cancellationToken);
                File.SetLastWriteTimeUtc(file, DateTime.UtcNow);
                await Task.Delay(700, cancellationToken);
            }
            Assert.Null(await fixture.RowAsync(name, cancellationToken));
            Assert.True(File.Exists(file));
        }
        finally
        {
            await worker.StopAsync(cancellationToken);
        }
    }

    [Fact]
    public async Task A_file_with_MaxAttempts_banked_rows_is_moved_to_processed_without_a_new_row()
    {
        await using var fixture = new Fixture();
        var cancellationToken = TestContext.Current.CancellationToken;
        var name = "test__max_" + Guid.NewGuid().ToString("N")[..8] + ".pdf";
        var file = Path.Combine(fixture.Paths.InboxPath, name);
        await File.WriteAllBytesAsync(file, [1, 2, 3, 4], cancellationToken);
        File.SetLastWriteTimeUtc(file, DateTime.UtcNow - TimeSpan.FromSeconds(90));
        await fixture.AddBankedRowsAsync(name, 4, fixture.Ingest.MaxAttempts, cancellationToken);

        try
        {
            await RunUntil(fixture, () => Task.FromResult(File.Exists(Path.Combine(fixture.Paths.ProcessedPath, name))), cancellationToken);

            Assert.True(File.Exists(Path.Combine(fixture.Paths.ProcessedPath, name)));
            Assert.False(File.Exists(file));
            Assert.Equal(fixture.Ingest.MaxAttempts, await fixture.AttemptsAsync(name, 4, cancellationToken));
        }
        finally
        {
            await fixture.RemoveRowsAsync(name, cancellationToken);
        }
    }
}
