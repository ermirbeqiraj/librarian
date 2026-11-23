using Microsoft.IdentityModel.Tokens;

namespace Api.Features.Auth;

internal sealed class AccessKeys
{
    internal const string HttpClientName = "access-keys";

    private static readonly TimeSpan CacheAge = TimeSpan.FromHours(1);

    private readonly HttpClient http;
    private readonly string certsUrl;
    private readonly SemaphoreSlim gate = new(1, 1);
    private Dictionary<string, SecurityKey>? byKid;
    private DateTimeOffset fetched;

    public AccessKeys(HttpClient http, string certsUrl)
    {
        this.http = http;
        this.certsUrl = certsUrl;
    }

    internal async Task<IReadOnlyCollection<SecurityKey>> KeysAsync(string? kid, CancellationToken cancellationToken)
    {
        var cached = byKid;
        if (cached is not null
            && DateTimeOffset.UtcNow - fetched < CacheAge
            && (kid is null || cached.ContainsKey(kid)))
        {
            return [.. cached.Values];
        }

        await gate.WaitAsync(cancellationToken);
        try
        {
            if (byKid is null
                || DateTimeOffset.UtcNow - fetched >= CacheAge
                || (kid is not null && !byKid.ContainsKey(kid)))
            {
                await FetchAsync(cancellationToken);
            }

            return [.. byKid!.Values];
        }
        finally
        {
            gate.Release();
        }
    }

    private async Task FetchAsync(CancellationToken cancellationToken)
    {
        using var response = await http.GetAsync(certsUrl, cancellationToken);
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        var set = new JsonWebKeySet(json);
        var byKid = new Dictionary<string, SecurityKey>();
        foreach (var key in set.GetSigningKeys())
        {
            if (key.KeyId is { Length: > 0 } id)
            {
                byKid[id] = key;
            }
        }

        if (byKid.Count == 0)
            throw new InvalidOperationException($"The certs document at '{certsUrl}' holds no signing keys.");

        this.byKid = byKid;
        fetched = DateTimeOffset.UtcNow;
    }
}
