using Application.Domain;

namespace Tests.Store;

public sealed class IngestionDomainTests
{
    [Fact]
    public void A_new_ingestion_starts_started()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        Assert.Equal(IngestionState.Started, ingestion.State);
        Assert.Equal("a.pdf", ingestion.FileName);
        Assert.Equal(10, ingestion.FileSize);
        Assert.Equal(0, ingestion.Tries);
    }

    [Fact]
    public void MarkRead_hashes_the_text_sha256_lowercase_hex()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        ingestion.MarkRead(ReadBy.Docling, "abc");
        Assert.Equal("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", ingestion.TextHash);
    }

    [Fact]
    public void MarkRead_keeps_the_state_and_holds_the_text()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        ingestion.MarkRead(ReadBy.Ocr, "text");
        Assert.Equal(IngestionState.Started, ingestion.State);
        Assert.Equal(ReadBy.Ocr, ingestion.ReadBy);
        Assert.Equal("text", ingestion.ReadText);
        Assert.Equal("982d9e3eb996f559e633f4d194def3761d909f5a3b647d1a851fead67c32c9d1", ingestion.TextHash);
    }

    [Fact]
    public void MarkExtracted_and_MarkEmbedded_move_the_state_and_clear_the_error()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        ingestion.MarkError(IngestionErrorReason.ReadFailed, "boom");
        ingestion.MarkRead(ReadBy.Docling, "text");
        ingestion.MarkExtracted("{}");
        Assert.Equal(IngestionState.Extracted, ingestion.State);
        Assert.Null(ingestion.ErrorReason);
        Assert.Equal("{}", ingestion.ExtractedJson);

        var document = Document.Create(new Application.Handlers.Ingest.Extract.Extracted(
            "invoice", new Application.Handlers.Ingest.Extract.Validity("2026-01-01", "2026-12-31", "2026"), "an invoice", []));
        ingestion.MarkEmbedded(document);
        Assert.Equal(IngestionState.Embedded, ingestion.State);
        Assert.Same(document, ingestion.Document);
    }

    [Fact]
    public void MarkError_clears_the_document_link()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        var document = Document.Create(new Application.Handlers.Ingest.Extract.Extracted(
            "invoice", new Application.Handlers.Ingest.Extract.Validity("2026-01-01", "2026-12-31", "2026"), "an invoice", []));
        ingestion.MarkEmbedded(document);
        ingestion.MarkError(IngestionErrorReason.SaveFailed, "db down");
        Assert.Equal(IngestionState.Error, ingestion.State);
        Assert.Equal(IngestionErrorReason.SaveFailed, ingestion.ErrorReason);
        Assert.Null(ingestion.Document);
        Assert.Null(ingestion.DocumentId);
    }

    [Fact]
    public void CountTry_counts_and_touches()
    {
        var ingestion = Ingestion.Create("a.pdf", 10);
        var before = ingestion.UpdatedAt;
        ingestion.CountTry();
        Assert.Equal(1, ingestion.Tries);
        Assert.True(ingestion.UpdatedAt >= before);
    }
}
