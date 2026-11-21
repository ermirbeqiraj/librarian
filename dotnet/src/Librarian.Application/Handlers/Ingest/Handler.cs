using System.Text.Json;
using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Ports.Ingest;
using Microsoft.Agents.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Librarian.Application.Handlers.Ingest;

public sealed class IngestHandler(
    ILogger<IngestHandler> logger,
    [FromKeyedServices("doclingReader")] IDocumentReader doclingReader,
    [FromKeyedServices("ocrReader")] IDocumentReader ocrReader,
    IOcrBudget ocrBudget,
    IIngestFileStore fileStore,
    [FromKeyedServices("extractAgent")] AIAgent extractAgent,
    IExtractRunOptionsFactory extractRunOptionsFactory,
    ExtractMessageBuilder messageBuilder,
    IngestOptions ingestOptions) : IIngestHandler
{
    public async Task HandleAsync(IngestFile file, CancellationToken cancellationToken)
    {
        try
        {
            var pages = await ReadAsync(file, cancellationToken);
            var text = string.Join("\n\n", pages.Select(p => p.Markdown));
            var message = messageBuilder.Build(file.Name, pages, ingestOptions.Extract.HeadPages, ingestOptions.Extract.TailPages);

            var session = await extractAgent.CreateSessionAsync(cancellationToken);
            var runOptions = extractRunOptionsFactory.Create(text);
            var extracted = await RunExtractedAsync(message, session, runOptions, cancellationToken);

            var verified = extracted with
            {
                Fields = [.. extracted.Fields.Select(f => f with { Verified = FieldVerifier.FoundIn(text, f.AsWritten) })],
            };
            await WriteResultAsync(file, new IngestResult(file.Name, "extracted", verified, null), cancellationToken);
            var unverified = verified.Fields.Count(f => !f.Verified);
            logger.LogInformation("Ingested {File}: kind {Kind}, {Fields} field(s), {Unverified} not verified",
                file.Name, verified.Kind, verified.Fields.Count, unverified);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogError(ex, "Failed {File}: {Message}", file.Name, ex.Message);
            await WriteResultAsync(file, new IngestResult(file.Name, "failed", null, ex.Message), cancellationToken);
        }

        await fileStore.MoveToProcessedAsync(file.Path, cancellationToken);
    }

    private async Task<IReadOnlyList<Page>> ReadAsync(IngestFile file, CancellationToken cancellationToken)
    {
        IReadOnlyList<Page>? pages = null;
        try
        {
            pages = await doclingReader.ReadAsync(file.Path, cancellationToken);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogWarning("Docling failed on {File}: {Message}", file.Name, ex.Message);
        }

        if (pages is not null && !ReaderFailure.IsFailure(pages, ingestOptions.Ocr.MinCharsPerPage))
            return pages;

        if (!ocrBudget.TrySpend(out var refusal))
            throw new InvalidOperationException($"Docling could not read {file.Name} and the OCR budget refused a call: {refusal}");

        logger.LogInformation("Docling failed on {File}; reading with OCR", file.Name);
        return await ocrReader.ReadAsync(file.Path, cancellationToken);
    }

    private async Task<Extracted> RunExtractedAsync(string message, AgentSession session, AgentRunOptions runOptions, CancellationToken cancellationToken)
    {
        const int maxParseRetries = 2;
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                var response = await extractAgent.RunAsync<Extracted>(message, session, ExtractJson.Options, runOptions, cancellationToken);
                return response.Result;
            }
            catch (JsonException) when (attempt < maxParseRetries)
            {
                logger.LogWarning("The extract reply was not valid JSON; asking again (attempt {Attempt})", attempt + 1);
                message = "Your last answer was not a raw JSON object. Answer with the whole corrected object as raw JSON only: no markdown fences, no commentary.";
            }
        }
    }

    private Task WriteResultAsync(IngestFile file, IngestResult result, CancellationToken cancellationToken)
        => fileStore.WriteResultAsync(file.Name, JsonSerializer.Serialize(result, ExtractJson.Options), cancellationToken);
}
