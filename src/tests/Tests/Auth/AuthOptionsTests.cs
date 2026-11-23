using Api.Features.Auth;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Hosting;

namespace Tests.Auth;

public sealed class AuthOptionsTests
{
    private static IHostEnvironment Env(string name) => new HostEnvironment
    {
        EnvironmentName = name,
    };

    private static IConfiguration Config(params (string Key, string Value)[] pairs)
    {
        var builder = new ConfigurationBuilder();
        builder.AddInMemoryCollection(pairs.Select(p => new KeyValuePair<string, string?>(p.Key, p.Value)));
        return builder.Build();
    }

    [Fact]
    public void Development_is_bearer_and_everything_else_is_access()
    {
        Assert.Equal(AuthOptions.BearerMode, AuthOptions.ModeFor(Env(Environments.Development)));
        Assert.Equal(AuthOptions.AccessMode, AuthOptions.ModeFor(Env(Environments.Production)));
        Assert.Equal(AuthOptions.AccessMode, AuthOptions.ModeFor(Env("Homeserver")));
    }

    [Fact]
    public void A_development_environment_refuses_to_start_without_a_bearer_token()
    {
        var services = new ServiceCollection();
        var error = Assert.Throws<InvalidOperationException>(() =>
            services.AddAuth(Config(), Env(Environments.Development)));
        Assert.Equal("Auth:Bearer:Token is not set.", error.Message);
    }

    [Fact]
    public void A_development_environment_starts_with_a_bearer_token()
    {
        var services = new ServiceCollection();
        services.AddAuth(
            Config(("Auth:Bearer:Token", new string('a', 43))),
            Env(Environments.Development));
    }

    [Fact]
    public void A_bearer_token_shorter_than_32_characters_is_refused()
    {
        var services = new ServiceCollection();
        var error = Assert.Throws<InvalidOperationException>(() =>
            services.AddAuth(Config(("Auth:Bearer:Token", "short")), Env(Environments.Development)));
        Assert.Equal("Auth:Bearer:Token must be at least 32 characters.", error.Message);
    }

    [Fact]
    public void A_production_environment_refuses_to_start_without_an_audience()
    {
        var services = new ServiceCollection();
        var error = Assert.Throws<InvalidOperationException>(() =>
            services.AddAuth(
                Config(("Auth:Access:TeamDomain", "team.cloudflareaccess.com")),
                Env(Environments.Production)));
        Assert.Equal("Auth:Access:Audience is not set.", error.Message);
    }

    [Fact]
    public void A_production_environment_starts_with_the_access_keys()
    {
        var services = new ServiceCollection();
        services.AddAuth(
            Config(
                ("Auth:Access:TeamDomain", "team.cloudflareaccess.com"),
                ("Auth:Access:Audience", "test")),
            Env(Environments.Production));
    }

    [Fact]
    public void A_certs_url_that_is_not_a_url_is_refused()
    {
        var services = new ServiceCollection();
        var error = Assert.Throws<InvalidOperationException>(() =>
            services.AddAuth(
                Config(
                    ("Auth:Access:TeamDomain", "team.cloudflareaccess.com"),
                    ("Auth:Access:Audience", "test"),
                    ("Auth:Access:CertsUrl", "not-a-url")),
                Env(Environments.Production)));
        Assert.Equal("Auth:Access:CertsUrl must be an absolute http(s) URL.", error.Message);
    }

    [Fact]
    public void An_auth_mode_in_config_refuses_to_start_with_a_message_saying_the_environment_decides()
    {
        var services = new ServiceCollection();
        var error = Assert.Throws<InvalidOperationException>(() =>
            services.AddAuth(
                Config(
                    ("Auth:Mode", "bearer"),
                    ("Auth:Bearer:Token", new string('a', 43))),
                Env(Environments.Development)));
        Assert.Equal(
            "Auth:Mode is not a setting anymore: the environment decides (Development = bearer, everything else = access).",
            error.Message);
    }

    private sealed class HostEnvironment : IHostEnvironment
    {
        public string ApplicationName { get; set; } = "";
        public string EnvironmentName { get; set; } = "";
        public string ContentRootPath { get; set; } = "";
        public IFileProvider ContentRootFileProvider { get; set; } = new NullFileProvider();
    }
}
