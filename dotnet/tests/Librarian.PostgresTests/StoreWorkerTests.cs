using System.Text.Json;
using Librarian.Adapters;
using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Handlers.Store;
using Librarian.Application.Ports.Store;
using Librarian.Ingest;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;

namespace Librarian.PostgresTests;

[Collection("Postgres")]
public sealed class StoreWorkerTests
{
    private sealed class FakeEmbedder : IEmbeddingGenerator<string, Embedding<float>>
    {
        public string? ThrowOnMarker { get; set; }
        public List<string> SeenInputs { get; } = [];
        private bool _thrown;

        public EmbeddingGeneratorMetadata Metadata => new("fake", null, "fake");

        public Task<GeneratedEmbeddings<Embedding<float>>> GenerateAsync(
            IEnumerable<string> values, EmbeddingGenerationOptions? options = null, CancellationToken cancellationToken = default)
        {
            var texts = values.ToList();
            SeenInputs.Add(texts[0]);
            if (ThrowOnMarker is not null && !_thrown && texts[0].Contains(ThrowOnMarker))
            {
                _thrown = true;
                throw new IOException("tei is down");
            }
            return Task.FromResult(new GeneratedEmbeddings<Embedding<float>>(
                texts.Select(_ => new Embedding<float>(new float[1024]))));
        }

        public object? GetService(Type serviceType, object? serviceKey = null) => null;

        public void Dispose()
        {
        }
    }

    private sealed class FakeTokenCounter : ITokenCounter
    {
        public Task<int> CountAsync(string text, CancellationToken cancellationToken)
            => Task.FromResult(text.Length / 10 + 1);
    }

    private sealed class Fixture : IAsyncDisposable
    {
        public ServiceProvider Provider { get; }
        public FakeEmbedder Embedder { get; } = new();
        public string Marker { get; } = Guid.NewGuid().ToString("N")[..8];
        public StoreOptions StoreOptions { get; } = new()
        {
            ScanIntervalSeconds = 1,
            MaxTries = 3,
            Embedding = new StoreOptions.EmbeddingOptions
            {
                Url = "http://127.0.0.1:8083", Model = "fake", Dimensions = 1024, TokenBudget = 8176, BatchSize = 32, TimeoutSeconds = 5,
            },
        };

        public Fixture()
        {
            var config = new ConfigurationBuilder()
                .SetBasePath(Path.Combine(SolutionRoot.Find(), "src", "Librarian.Ingest"))
                .AddJsonFile("appsettings.json", optional: false)
                .AddJsonFile("appsettings.Development.json", optional: true)
                .AddEnvironmentVariables()
                .Build();
            var connectionString = config.GetConnectionString("Postgres")
                ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
            var services = new ServiceCollection();
            services.AddLogging();
            services.AddPostgres(connectionString);
            services.AddSingleton<IEmbeddingGenerator<string, Embedding<float>>>(Embedder);
            services.AddSingleton<ITokenCounter, FakeTokenCounter>();
            services.AddSingleton(StoreOptions);
            services.AddStoreHandler();
            Provider = services.BuildServiceProvider();
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            db.Ingestions.RemoveRange(db.Ingestions.Where(i => EF.Functions.Like(i.FileName, @"test\_%")));
            db.SaveChanges();
        }

        public async Task<long> AddExtractedRow(string name, string text, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            var extracted = new Extracted("invoice", new Validity("2026-01-01", null, "2026"), "test doc",
                [new ExtractedField("issuer", "ACME", "ACME", true)]);
            var ingestion = Ingestion.Create(name, 1);
            db.Ingestions.Add(ingestion);
            await db.SaveChangesAsync(cancellationToken);
            ingestion.MarkRead(ReadBy.Docling, Marker + " " + text);
            ingestion.MarkExtracted(JsonSerializer.Serialize(extracted, ExtractJson.Options));
            await db.SaveChangesAsync(cancellationToken);
            return ingestion.Id;
        }

        public async Task<Ingestion?> LoadIngestion(long id, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            return await db.Ingestions.SingleOrDefaultAsync(i => i.Id == id, cancellationToken);
        }

        public async Task RemoveIngestion(long id, CancellationToken cancellationToken)
        {
            using var scope = Provider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            var ingestion = await db.Ingestions.SingleAsync(i => i.Id == id, cancellationToken);
            db.Ingestions.Remove(ingestion);
            await db.SaveChangesAsync(cancellationToken);
            var document = await db.Documents.SingleOrDefaultAsync(d => d.Id == ingestion.DocumentId, cancellationToken);
            if (document is not null)
            {
                db.Documents.Remove(document);
                await db.SaveChangesAsync(cancellationToken);
            }
        }

        public async ValueTask DisposeAsync() => await Provider.DisposeAsync();
    }

    private static async Task RunWorker(Fixture fixture, Func<Task<bool>> until, CancellationToken cancellationToken)
    {
        var worker = new StoreWorker(
            NullLogger<StoreWorker>.Instance,
            fixture.Provider.GetRequiredService<IServiceScopeFactory>(),
            fixture.StoreOptions);
        await worker.StartAsync(cancellationToken);
        try
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(30);
            while (!await until() && DateTime.UtcNow < deadline)
                await Task.Delay(200, cancellationToken);
        }
        finally
        {
            await worker.StopAsync(cancellationToken);
        }
    }

    [Fact]
    public async Task The_worker_takes_the_oldest_row_first_and_moves_on_until_none_is_left()
    {
        await using var fixture = new Fixture();
        var cancellationToken = TestContext.Current.CancellationToken;
        var first = await fixture.AddExtractedRow("test__worker_first.pdf", "text zero", cancellationToken);
        var second = await fixture.AddExtractedRow("test__worker_second.pdf", "text one", cancellationToken);
        try
        {
            await RunWorker(fixture, async () =>
            {
                var a = await fixture.LoadIngestion(first, cancellationToken);
                var b = await fixture.LoadIngestion(second, cancellationToken);
                return a is { State: IngestionState.Embedded } && b is { State: IngestionState.Embedded };
            }, cancellationToken);

            var zeroIndex = fixture.Embedder.SeenInputs.FindIndex(i => i.Contains(fixture.Marker + " text zero"));
            var oneIndex = fixture.Embedder.SeenInputs.FindIndex(i => i.Contains(fixture.Marker + " text one"));
            Assert.True(zeroIndex >= 0 && oneIndex > zeroIndex, "the oldest row must be embedded first");
            var a = await fixture.LoadIngestion(first, cancellationToken);
            var b = await fixture.LoadIngestion(second, cancellationToken);
            Assert.Equal(IngestionState.Embedded, a!.State);
            Assert.Equal(IngestionState.Embedded, b!.State);
            Assert.NotNull(a.DocumentId);
            Assert.NotNull(b.DocumentId);
        }
        finally
        {
            await fixture.RemoveIngestion(first, cancellationToken);
            await fixture.RemoveIngestion(second, cancellationToken);
        }
    }

    [Fact]
    public async Task A_failed_row_is_banked_as_an_error_and_the_worker_moves_on_then_retries_it_on_a_later_tick()
    {
        await using var fixture = new Fixture();
        fixture.Embedder.ThrowOnMarker = fixture.Marker;
        var cancellationToken = TestContext.Current.CancellationToken;
        var first = await fixture.AddExtractedRow("test__worker_fail.pdf", "text zero", cancellationToken);
        var second = await fixture.AddExtractedRow("test__worker_ok.pdf", "text one", cancellationToken);
        try
        {
            await RunWorker(fixture, async () =>
            {
                var a = await fixture.LoadIngestion(first, cancellationToken);
                var b = await fixture.LoadIngestion(second, cancellationToken);
                return a is { State: IngestionState.Embedded } && b is { State: IngestionState.Embedded };
            }, cancellationToken);

            var a = await fixture.LoadIngestion(first, cancellationToken);
            Assert.Equal(IngestionState.Embedded, a!.State);
            Assert.Equal(1, a.Tries);
            Assert.Null(a.ErrorReason);
            var zeroIndex = fixture.Embedder.SeenInputs.FindIndex(i => i.Contains(fixture.Marker + " text zero"));
            var oneIndex = fixture.Embedder.SeenInputs.FindIndex(i => i.Contains(fixture.Marker + " text one"));
            Assert.True(zeroIndex >= 0 && oneIndex > zeroIndex, "the failed oldest row must be handled before the next one");
        }
        finally
        {
            await fixture.RemoveIngestion(first, cancellationToken);
            await fixture.RemoveIngestion(second, cancellationToken);
        }
    }
}
