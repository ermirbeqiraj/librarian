using System.Text.Json;
using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Ports.Store;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging;

namespace Librarian.Application.Handlers.Store;

public sealed class StoreHandler(
    ILogger<StoreHandler> logger,
    LibrarianDbContext db,
    IEmbeddingGenerator<string, Embedding<float>> embedder,
    ITokenCounter tokenCounter,
    StoreOptions storeOptions)
{
    public async Task HandleAsync(long ingestionId, CancellationToken cancellationToken)
    {
        var ingestion = await db.Ingestions.FirstAsync(i => i.Id == ingestionId, cancellationToken);
        if (ingestion.ReadText is null || ingestion.ExtractedJson is null)
            throw new InvalidOperationException($"Ingestion {ingestionId} is {ingestion.State} without a read; the worker should not have taken it.");
        var extracted = JsonSerializer.Deserialize<Extracted>(ingestion.ExtractedJson, ExtractJson.Options)
            ?? throw new InvalidOperationException($"Ingestion {ingestionId} has an unreadable extracted record.");

        var embedding = true;
        Document? document = null;
        try
        {
            var (sections, chunkTexts) = await ChunkAsync(ingestion.ReadText, extracted, cancellationToken);
            var generated = await embedder.GenerateAsync(chunkTexts, cancellationToken: cancellationToken);
            List<Embedding<float>> vectors = [.. generated];
            if (vectors.Count != chunkTexts.Count)
                throw new InvalidOperationException($"TEI returned {vectors.Count} vectors for {chunkTexts.Count} chunks.");
            foreach (var vector in vectors)
            {
                if (vector.Vector.Length != storeOptions.Embedding.Dimensions)
                    throw new InvalidOperationException($"TEI returned a {vector.Vector.Length}-d vector, expected {storeOptions.Embedding.Dimensions}.");
            }

            embedding = false;
            document = Document.Create(extracted);
            var vectorIndex = 0;
            foreach (var (heading, text, chunks) in sections)
            {
                var section = document.AddSection(heading, text);
                foreach (var _ in chunks)
                    section.AddChunk(chunkTexts[vectorIndex], vectors[vectorIndex++].Vector.ToArray());
            }
            db.Documents.Add(document);
            ingestion.MarkEmbedded(document);
            await db.SaveChangesAsync(cancellationToken);
            logger.LogInformation("Ingestion {IngestionId}: embedded as document {DocumentId}, {Sections} section(s), {Chunks} chunk(s)",
                ingestion.Id, document.Id, sections.Count, chunkTexts.Count);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            if (document is not null)
                db.Entry(document).State = EntityState.Detached;
            var reason = embedding ? IngestionErrorReason.EmbedFailed : IngestionErrorReason.SaveFailed;
            await FailAsync(ingestion, reason, ex, cancellationToken);
        }
    }

    private async Task<(List<(string Heading, string Text, List<string> Chunks)> Sections, List<string> ChunkTexts)> ChunkAsync(
        string text, Extracted extracted, CancellationToken cancellationToken)
    {
        var prefix = Prefix(extracted);
        var chunker = new Chunker(storeOptions.Embedding.TokenBudget, tokenCounter.CountAsync);
        var sections = new List<(string, string, List<string>)>();
        var chunkTexts = new List<string>();
        foreach (var (heading, sectionText) in Sections.FromMarkdown(text))
        {
            var header = heading.Length > 0 ? $"{prefix}\n{heading}" : prefix;
            var chunks = await chunker.ChunkAsync(header, sectionText, cancellationToken);
            sections.Add((heading, sectionText, chunks));
            chunkTexts.AddRange(chunks);
        }
        return (sections, chunkTexts);
    }

    private static string Prefix(Extracted extracted)
    {
        var issuer = extracted.Fields.FirstOrDefault(f => f.Name.Equals("issuer", StringComparison.OrdinalIgnoreCase))?.Value;
        return issuer is null
            ? $"{extracted.Kind} — {extracted.Description}"
            : $"{extracted.Kind} — {issuer} — {extracted.Description}";
    }

    private async Task FailAsync(Ingestion ingestion, IngestionErrorReason reason, Exception ex, CancellationToken cancellationToken)
    {
        ingestion.CountTry();
        ingestion.MarkError(reason, ex.Message);
        await db.SaveChangesAsync(cancellationToken);
        logger.LogError(ex, "Ingestion {IngestionId} failed to store ({Reason}), try {Tries}: {Message}",
            ingestion.Id, reason, ingestion.Tries, ex.Message);
    }
}
