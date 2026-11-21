using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;

namespace Librarian.Adapters.Mistral;

public sealed class MistralOcrReader(IHttpClientFactory httpClientFactory, IngestOptions ingest, MistralOptions mistral) : IDocumentReader
{
    public async Task<IReadOnlyList<Page>> ReadAsync(string path, CancellationToken cancellationToken)
    {
        var client = httpClientFactory.CreateClient("ocrReader");
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", mistral.ApiKey);

        var encoded = Convert.ToBase64String(await File.ReadAllBytesAsync(path, cancellationToken));
        var pages = Enumerable.Range(0, ingest.Ocr.MaxPages).ToArray();
        var request = new OcrRequest(
            ingest.Ocr.Model,
            new OcrDocument("document_url", $"data:application/pdf;base64,{encoded}"),
            pages);

        using var response = await client.PostAsJsonAsync("", request, cancellationToken);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<OcrResponse>(cancellationToken)
            ?? throw new InvalidOperationException("Mistral OCR returned an empty response.");

        return [.. result.Pages
            .OrderBy(p => p.Index)
            .Select(p => new Page(p.Index + 1, p.Markdown))];
    }

    private sealed record OcrRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("document")] OcrDocument Document,
        [property: JsonPropertyName("pages")] int[] Pages);

    private sealed record OcrDocument(
        [property: JsonPropertyName("type")] string Type,
        [property: JsonPropertyName("document_url")] string DocumentUrl);

    private sealed record OcrResponse([property: JsonPropertyName("pages")] List<OcrPage> Pages);

    private sealed record OcrPage(
        [property: JsonPropertyName("index")] int Index,
        [property: JsonPropertyName("markdown")] string Markdown);
}
