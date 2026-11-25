using System.Text.Json;
using Application.Domain;
using Application.Handlers.Ingest.Extract;
using Application.Ports.Ingest;
using Microsoft.Agents.AI;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Application.Handlers.Ingest;

public sealed class IngestHandler(
    ILogger<IngestHandler> logger,
    LibrarianDbContext db,
    [FromKeyedServices("doclingReader")] IDocumentReader doclingReader,
    [FromKeyedServices("ocrReader")] IDocumentReader ocrReader,
    IIngestFileStore fileStore,
    [FromKeyedServices("extractAgent")] AIAgent extractAgent,
    IExtractRunOptionsFactory extractRunOptionsFactory,
    ExtractMessageBuilder messageBuilder,
    IngestOptions ingestOptions)
{
    public async Task HandleAsync(IngestFile file, CancellationToken cancellationToken)
    {
        var ingestion = Ingestion.Create(file.Name, file.Size);
        db.Ingestions.Add(ingestion);
        await db.SaveChangesAsync(cancellationToken);

        var reading = true;
        try
        {
            var read = await ReadAsync(file, cancellationToken);
            var text = string.Join("\n\n", read.Pages.Select(p => p.Markdown));
            ingestion.MarkRead(read.ReadBy, text);

            if (await IsDuplicateAsync(ingestion, cancellationToken))
            {
                ingestion.MarkError(IngestionErrorReason.Duplicate, "The read text is already on an embedded ingestion.");
                await db.SaveChangesAsync(cancellationToken);
                logger.LogWarning("Ingestion {IngestionId} of {File}: duplicate, the file is deleted", ingestion.Id, file.Name);
                await fileStore.DeleteAsync(file.Path, cancellationToken);
                return;
            }

            reading = false;
            var message = messageBuilder.Build(file.Name, read.Pages, ingestOptions.Extract.HeadPages, ingestOptions.Extract.TailPages);
            var session = await extractAgent.CreateSessionAsync(cancellationToken);
            var runOptions = extractRunOptionsFactory.Create(text);
            var extracted = await RunExtractedAsync(message, session, runOptions, cancellationToken);

            var verified = extracted with
            {
                Fields = [.. extracted.Fields.Select(f => f with { Verified = FieldVerifier.FoundIn(text, f.AsWritten) })],
            };
            ingestion.MarkExtracted(JsonSerializer.Serialize(verified, ExtractJson.Options));
            await db.SaveChangesAsync(cancellationToken);
            var unverified = verified.Fields.Count(f => !f.Verified);
            logger.LogInformation("Ingestion {IngestionId} of {File}: kind {Kind}, {Fields} field(s), {Unverified} not verified",
                ingestion.Id, file.Name, verified.Kind, verified.Fields.Count, unverified);

            var filedPath = $"{Slug(verified.Kind)}/{ingestion.CreatedAt:yyyy-MM}/{ingestion.Id}{Path.GetExtension(file.Name)}";
            await fileStore.MoveToProcessedAsync(file.Path, filedPath, cancellationToken);
            ingestion.MarkFiled(filedPath);
            await db.SaveChangesAsync(cancellationToken);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            var reason = reading ? IngestionErrorReason.ReadFailed : IngestionErrorReason.ExtractFailed;
            ingestion.MarkError(reason, ex.Message);
            await db.SaveChangesAsync(cancellationToken);
            logger.LogError(ex, "Ingestion {IngestionId} of {File} failed ({Reason}): {Message}", ingestion.Id, file.Name, reason, ex.Message);
            var quarantinePath = $"{ingestion.CreatedAt:yyyy-MM}/{ingestion.Id}{Path.GetExtension(file.Name)}";
            await fileStore.MoveToQuarantineAsync(file.Path, quarantinePath, cancellationToken);
            return;
        }
    }

    private static string Slug(string kind)
    {
        var chars = kind.Trim().ToLowerInvariant().Select(c => char.IsLetterOrDigit(c) ? c : '_').ToArray();
        return string.Join('_', new string(chars).Split('_', StringSplitOptions.RemoveEmptyEntries));
    }

    private async Task<Read> ReadAsync(IngestFile file, CancellationToken cancellationToken)
    {
        try
        {
            var pages = await doclingReader.ReadAsync(file.Path, cancellationToken);
            if (!ReaderFailure.IsFailure(pages, ingestOptions.Ocr.MinCharsPerPage))
                return new Read(pages, ReadBy.Docling);
            logger.LogWarning("Docling read too little of {File}", file.Name);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogWarning("Docling failed on {File}: {Message}", file.Name, ex.Message);
        }

        logger.LogInformation("Reading {File} with OCR", file.Name);
        const int attempts = 3;
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                var ocrPages = await ocrReader.ReadAsync(file.Path, cancellationToken);
                return new Read(ocrPages, ReadBy.Ocr);
            }
            catch (Exception ex) when (ex is not OperationCanceledException && attempt < attempts)
            {
                logger.LogWarning("OCR attempt {Attempt}/{Attempts} on {File} failed: {Message}", attempt, attempts, file.Name, ex.Message);
            }
        }
    }

    private Task<bool> IsDuplicateAsync(Ingestion ingestion, CancellationToken cancellationToken)
    {
        if (ingestion.TextHash is not { } hash)
            throw new InvalidOperationException($"Ingestion {ingestion.Id} has no text hash after MarkRead.");
        return db.Ingestions.AnyAsync(i => i.TextHash == hash && i.State == IngestionState.Embedded, cancellationToken);
    }

    private async Task<Extracted> RunExtractedAsync(string message, AgentSession session, AgentRunOptions runOptions, CancellationToken cancellationToken)
    {
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                var response = await extractAgent.RunAsync<Extracted>(message, session, ExtractJson.Options, runOptions, cancellationToken);
                return response.Result;
            }
            catch (JsonException) when (attempt < ingestOptions.Extract.ParseRetries)
            {
                logger.LogWarning("The extract reply was not valid JSON; asking again (attempt {Attempt})", attempt + 1);
                message = "Your last answer was not a raw JSON object. Answer with the whole corrected object as raw JSON only: no markdown fences, no commentary.";
            }
        }
    }

    private sealed record Read(IReadOnlyList<Page> Pages, ReadBy ReadBy);
}
