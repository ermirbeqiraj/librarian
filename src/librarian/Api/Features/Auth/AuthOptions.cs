using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Hosting;

namespace Api.Features.Auth;

internal sealed class AuthOptions
{
    public const string AccessMode = "access";
    public const string BearerMode = "bearer";

    public AccessOptions Access { get; set; } = new();
    public BearerOptions Bearer { get; set; } = new();

    public static string ModeFor(IHostEnvironment environment) =>
        environment.IsDevelopment() ? BearerMode : AccessMode;

    public void Validate(string mode)
    {
        if (mode == BearerMode)
        {
            Bearer.Validate();
        }
        else
        {
            Access.Validate();
        }
    }
}

internal sealed class AccessOptions
{
    public string TeamDomain { get; set; } = "";
    public string Audience { get; set; } = "";
    public string? CertsUrl { get; set; }

    public string Issuer => $"https://{Team}/";
    public string Certs => CertsUrl ?? $"https://{Team}/cdn-cgi/access/certs";
    private string Team => Host(TeamDomain);

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(TeamDomain))
            throw new InvalidOperationException("Auth:Access:TeamDomain is not set.");
        if (string.IsNullOrWhiteSpace(Audience))
            throw new InvalidOperationException("Auth:Access:Audience is not set.");
        if (CertsUrl is { Length: > 0 } url
            && (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https")))
            throw new InvalidOperationException("Auth:Access:CertsUrl must be an absolute http(s) URL.");
    }

    private static string Host(string domain)
    {
        var host = domain.Trim().TrimEnd('/');
        var scheme = host.IndexOf("://", StringComparison.Ordinal);
        return scheme >= 0 ? host[(scheme + 3)..] : host;
    }
}

internal sealed class BearerOptions : AuthenticationSchemeOptions
{
    public string Token { get; set; } = "";
    public string? Name { get; set; }

    public override void Validate()
    {
        if (string.IsNullOrEmpty(Token))
            throw new InvalidOperationException("Auth:Bearer:Token is not set.");
        if (Token.Length < 32)
            throw new InvalidOperationException("Auth:Bearer:Token must be at least 32 characters.");
        base.Validate();
    }
}
