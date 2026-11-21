using System.Net.Http.Json;
using Librarian.Application.Handlers.Store;
using Microsoft.Extensions.AI;

namespace Librarian.Adapters.Tei;

public sealed class TeiEmbeddingGenerator(IHttpClientFactory httpClientFactory, StoreOptions store) : IEmbeddingGenerator<string, Embedding<float>>
{
    private readonly StoreOptions.EmbeddingOptions _embedding = store.Embedding;

    public EmbeddingGeneratorMetadata Metadata => new("tei", new Uri(_embedding.Url), _embedding.Model);

    public async Task<GeneratedEmbeddings<Embedding<float>>> GenerateAsync(
        IEnumerable<string> values, EmbeddingGenerationOptions? options = null, CancellationToken cancellationToken = default)
    {
        var texts = values.ToList();
        var embeddings = new List<Embedding<float>>(texts.Count);
        var client = httpClientFactory.CreateClient("tei");
        for (var start = 0; start < texts.Count; start += _embedding.BatchSize)
        {
            var batch = texts.Skip(start).Take(_embedding.BatchSize).ToList();
            var response = await client.PostAsJsonAsync("embed", new { inputs = batch }, cancellationToken);
            response.EnsureSuccessStatusCode();
            var rows = await response.Content.ReadFromJsonAsync<List<float[]>>(cancellationToken)
                ?? throw new InvalidOperationException("TEI /embed returned no vectors.");
            embeddings.AddRange(rows.Select(row => new Embedding<float>(row) { ModelId = _embedding.Model }));
        }
        return [.. embeddings];
    }

    public object? GetService(Type serviceType, object? serviceKey = null)
        => serviceType == typeof(IEmbeddingGenerator<string, Embedding<float>>) ? this : null;

    public void Dispose()
    {
    }
}
