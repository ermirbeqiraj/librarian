using System.Net;
using System.Security.Cryptography;
using Api.Features.Auth;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace Tests.Auth;

public sealed class AccessTokenValidationTests
{
    private static readonly AccessOptions Options = new()
    {
        TeamDomain = "team.cloudflareaccess.com",
        Audience = "test-aud",
    };

    private static (RsaSecurityKey Key, string Jwks) NewKey(string kid)
    {
        var key = new RsaSecurityKey(RSA.Create(2048)) { KeyId = kid };
        var parameters = key.Rsa!.ExportParameters(false);
        var jwks =
            $$"""
            {"keys":[{"kty":"RSA","use":"sig","alg":"RS256","kid":"{{kid}}",
            "n":"{{Base64UrlEncoder.Encode(parameters.Modulus)}}","e":"{{Base64UrlEncoder.Encode(parameters.Exponent)}}"}]}
            """;
        return (key, jwks);
    }

    private static string NewToken(
        RsaSecurityKey key,
        string issuer = "https://team.cloudflareaccess.com",
        string audience = "test-aud",
        DateTimeOffset? expires = null)
    {
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = issuer,
            Audience = audience,
            IssuedAt = ((expires ?? DateTimeOffset.UtcNow.AddMinutes(15)) - TimeSpan.FromMinutes(10)).UtcDateTime,
            NotBefore = ((expires ?? DateTimeOffset.UtcNow.AddMinutes(15)) - TimeSpan.FromMinutes(10)).UtcDateTime,
            Expires = (expires ?? DateTimeOffset.UtcNow.AddMinutes(15)).UtcDateTime,
            SigningCredentials = new SigningCredentials(key, SecurityAlgorithms.RsaSha256),
            Claims = new Dictionary<string, object>
            {
                ["sub"] = "test-sub",
                ["email"] = "ermir@example.com",
                ["name"] = "Ermir Test",
            },
        };
        return new JsonWebTokenHandler().CreateToken(descriptor);
    }

    private static async Task<TokenValidationResult> ValidateAsync(string token, AccessKeys keys) =>
        await new JsonWebTokenHandler().ValidateTokenAsync(
            token, AuthExtensions.AccessTokenValidationParameters(Options, keys));

    [Fact]
    public async Task A_token_signed_by_the_teams_keys_validates_with_its_claims()
    {
        var (key, jwks) = NewKey("key-1");
        using var http = new HttpClient(new CertsServer(jwks));
        var keys = new AccessKeys(http, Options.Certs);

        var result = await ValidateAsync(NewToken(key), keys);

        Assert.True(result.IsValid);
        Assert.Equal("test-sub", result.ClaimsIdentity.FindFirst("sub")?.Value);
        Assert.Equal("ermir@example.com", result.ClaimsIdentity.FindFirst("email")?.Value);
        Assert.Equal("Ermir Test", result.ClaimsIdentity.Name);
    }

    [Fact]
    public async Task A_token_signed_by_a_key_the_teams_dont_hold_is_refused()
    {
        var (servedKey, jwks) = NewKey("served");
        var (otherKey, _) = NewKey("other");
        using var http = new HttpClient(new CertsServer(jwks));
        var keys = new AccessKeys(http, Options.Certs);

        var result = await ValidateAsync(NewToken(otherKey), keys);

        Assert.False(result.IsValid);
    }

    [Fact]
    public async Task A_token_from_another_issuer_is_refused()
    {
        var (key, jwks) = NewKey("key-1");
        using var http = new HttpClient(new CertsServer(jwks));
        var keys = new AccessKeys(http, Options.Certs);

        var result = await ValidateAsync(NewToken(key, issuer: "https://stranger.cloudflareaccess.com"), keys);

        Assert.False(result.IsValid);
        Assert.IsType<SecurityTokenInvalidIssuerException>(result.Exception);
    }

    [Fact]
    public async Task A_token_for_another_audience_is_refused()
    {
        var (key, jwks) = NewKey("key-1");
        using var http = new HttpClient(new CertsServer(jwks));
        var keys = new AccessKeys(http, Options.Certs);

        var result = await ValidateAsync(NewToken(key, audience: "stranger"), keys);

        Assert.False(result.IsValid);
        Assert.IsType<SecurityTokenInvalidAudienceException>(result.Exception);
    }

    [Fact]
    public async Task An_expired_token_is_refused()
    {
        var (key, jwks) = NewKey("key-1");
        using var http = new HttpClient(new CertsServer(jwks));
        var keys = new AccessKeys(http, Options.Certs);

        var result = await ValidateAsync(NewToken(key, expires: DateTimeOffset.UtcNow.AddMinutes(-5)), keys);

        Assert.False(result.IsValid);
        Assert.IsType<SecurityTokenExpiredException>(result.Exception);
    }

    [Fact]
    public async Task The_keys_are_fetched_once_and_cached()
    {
        var (_, jwks) = NewKey("key-1");
        var server = new CertsServer(jwks);
        var keys = new AccessKeys(new HttpClient(server), Options.Certs);

        await keys.KeysAsync(null, TestContext.Current.CancellationToken);
        await keys.KeysAsync("key-1", TestContext.Current.CancellationToken);

        Assert.Equal(1, server.Requests);
    }

    [Fact]
    public async Task A_kid_the_cache_does_not_know_refetches()
    {
        var (_, jwks) = NewKey("key-1");
        var server = new CertsServer(jwks);
        var keys = new AccessKeys(new HttpClient(server), Options.Certs);

        await keys.KeysAsync("key-1", TestContext.Current.CancellationToken);
        await keys.KeysAsync("key-2", TestContext.Current.CancellationToken);

        Assert.Equal(2, server.Requests);
    }

    private sealed class CertsServer(string json) : HttpMessageHandler
    {
        public int Requests;

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Requests++;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json),
            });
        }
    }
}
