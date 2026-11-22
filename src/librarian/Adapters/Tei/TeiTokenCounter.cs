using System.Net.Http.Json;
using Application.Ports.Store;

namespace Adapters.Tei;

public sealed class TeiTokenCounter(IHttpClientFactory httpClientFactory) : ITokenCounter
{
    public async Task<int> CountAsync(string text, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(text))
            return 0;
        var client = httpClientFactory.CreateClient("tei");
        var response = await client.PostAsJsonAsync("tokenize", new { inputs = text, add_special_tokens = false }, cancellationToken);
        response.EnsureSuccessStatusCode();
        var rows = await response.Content.ReadFromJsonAsync<List<List<Token>>>(cancellationToken)
            ?? throw new InvalidOperationException("TEI /tokenize returned no tokens.");
        return rows.Sum(row => row.Count);
    }

    private sealed record Token(int Id);
}
