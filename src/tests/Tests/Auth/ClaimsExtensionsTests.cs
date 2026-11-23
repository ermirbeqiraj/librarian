using System.Security.Claims;
using Api.Features.Auth;

namespace Tests.Auth;

public sealed class ClaimsExtensionsTests
{
    private static ClaimsPrincipal Principal(params (string Type, string Value)[] claims)
    {
        var identity = new ClaimsIdentity(
            claims.Select(claim => new Claim(claim.Type, claim.Value)),
            "access");
        return new ClaimsPrincipal(identity);
    }

    [Fact]
    public void The_email_comes_from_the_email_claim_cloudflare_brings()
    {
        var principal = Principal(("email", "ermir@example.com"), ("sub", "uuid"));
        Assert.Equal("ermir@example.com", principal.Email());
    }

    [Fact]
    public void No_email_claim_is_null()
    {
        var principal = Principal(("sub", "uuid"));
        Assert.Null(principal.Email());
    }

    [Fact]
    public void The_name_comes_from_the_name_claim_when_the_identity_provider_brings_it()
    {
        var principal = Principal(("email", "ermir@example.com"), ("name", "Ermir"));
        Assert.Equal("Ermir", principal.Name());
    }

    [Fact]
    public void The_name_falls_back_to_the_common_name_claim()
    {
        var principal = Principal(("email", "connector@example.com"), ("common_name", "e367826f.access"));
        Assert.Equal("e367826f.access", principal.Name());
    }

    [Fact]
    public void An_identity_login_without_a_name_claim_is_null()
    {
        var principal = Principal(("email", "ermir@example.com"), ("sub", "uuid"), ("country", "IT"));
        Assert.Null(principal.Name());
    }
}
