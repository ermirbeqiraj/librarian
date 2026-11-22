using Librarian.Adapters;
using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest.Extract;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Librarian.PostgresTests;

[Collection("Postgres")]
public sealed class DbContextTests
{
    private static ServiceProvider Build()
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
        return services.BuildServiceProvider();
    }

    [Fact]
    public async Task An_ingestion_row_round_trips_through_its_states()
    {
        await using var provider = Build();
        using var scope = provider.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
        var cancellationToken = TestContext.Current.CancellationToken;

        var ingestion = Ingestion.Create("test__roundtrip.pdf", 123);
        db.Ingestions.Add(ingestion);
        await db.SaveChangesAsync(cancellationToken);
        var id = ingestion.Id;
        Assert.True(id > 0);

        db.ChangeTracker.Clear();
        var loaded = await db.Ingestions.SingleAsync(i => i.Id == id, cancellationToken);
        Assert.Equal(IngestionState.Started, loaded.State);
        Assert.Equal("test__roundtrip.pdf", loaded.FileName);
        loaded.MarkRead(ReadBy.Docling, "some text");
        loaded.MarkExtracted("""{"kind":"invoice"}""");
        await db.SaveChangesAsync(cancellationToken);

        db.ChangeTracker.Clear();
        loaded = await db.Ingestions.SingleAsync(i => i.Id == id, cancellationToken);
        Assert.Equal(IngestionState.Extracted, loaded.State);
        Assert.Equal(ReadBy.Docling, loaded.ReadBy);
        Assert.Equal("b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05aed2", loaded.TextHash);
        Assert.True(System.Text.Json.Nodes.JsonNode.DeepEquals(
            System.Text.Json.Nodes.JsonNode.Parse("""{"kind":"invoice"}"""),
            System.Text.Json.Nodes.JsonNode.Parse(loaded.ExtractedJson!)));

        loaded.MarkError(IngestionErrorReason.EmbedFailed, "tei down");
        loaded.CountTry();
        await db.SaveChangesAsync(cancellationToken);

        db.ChangeTracker.Clear();
        loaded = await db.Ingestions.SingleAsync(i => i.Id == id, cancellationToken);
        Assert.Equal(IngestionState.Error, loaded.State);
        Assert.Equal(IngestionErrorReason.EmbedFailed, loaded.ErrorReason);
        Assert.Equal(1, loaded.Tries);

        db.Ingestions.Remove(loaded);
        await db.SaveChangesAsync(cancellationToken);
    }

    [Fact]
    public async Task A_document_with_fields_sections_and_chunks_round_trips_with_vector_and_tsvector()
    {
        await using var provider = Build();
        using var scope = provider.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
        var cancellationToken = TestContext.Current.CancellationToken;

        var extracted = new Extracted(
            "invoice",
            new Validity("2026-01-01", null, "dal 2026"),
            "a test invoice",
            [new ExtractedField("issuer", "ACME", "ACME", true), new ExtractedField("total", "10", "10,00", false)]);
        var document = Document.Create(extracted);
        var section = document.AddSection("Invoice", "ACME\nTotal 10");
        section.AddChunk("invoice — ACME — a test invoice\nInvoice\nACME Total 10", new float[1024]);
        db.Documents.Add(document);
        var ingestion = Ingestion.Create("test__document.pdf", 5);
        db.Ingestions.Add(ingestion);
        await db.SaveChangesAsync(cancellationToken);
        ingestion.MarkEmbedded(document);
        await db.SaveChangesAsync(cancellationToken);

        var documentId = document.Id;
        var ingestionId = ingestion.Id;
        db.ChangeTracker.Clear();

        var loaded = await db.Documents
            .Include(d => d.Fields)
            .Include(d => d.Sections).ThenInclude(s => s.Chunks)
            .SingleAsync(d => d.Id == documentId, cancellationToken);
        Assert.Equal("invoice", loaded.Kind);
        Assert.Equal("2026-01-01", loaded.ValidityStart);
        Assert.Null(loaded.ValidityEnd);
        Assert.Equal(2, loaded.Fields.Count);
        var section0 = Assert.Single(loaded.Sections);
        Assert.Equal("Invoice", section0.Heading);
        var chunk = Assert.Single(section0.Chunks);
        Assert.Equal(1024, chunk.Embedding.Length);
        Assert.NotNull(db.Entry(chunk).Property("SearchText").CurrentValue);

        var loadedIngestion = await db.Ingestions.SingleAsync(i => i.Id == ingestionId, cancellationToken);
        Assert.Equal(IngestionState.Embedded, loadedIngestion.State);
        Assert.Equal(documentId, loadedIngestion.DocumentId);

        db.Ingestions.Remove(loadedIngestion);
        db.Documents.Remove(loaded);
        await db.SaveChangesAsync(cancellationToken);
    }
}
