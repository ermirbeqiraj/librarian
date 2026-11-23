using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Primitives;
using Microsoft.IdentityModel.Tokens;

namespace Api.Features.Auth;

internal static class AuthExtensions
{
    internal static IServiceCollection AddAuth(
        this IServiceCollection services,
        IConfiguration configuration,
        IHostEnvironment environment)
    {
        if (configuration.GetSection("Auth:Mode").Exists())
            throw new InvalidOperationException(
                "Auth:Mode is not a setting anymore: the environment decides (Development = bearer, everything else = access).");
        var auth = new AuthOptions
        {
            Access = configuration.GetSection("Auth:Access").Get<AccessOptions>() ?? new AccessOptions(),
            Bearer = configuration.GetSection("Auth:Bearer").Get<BearerOptions>() ?? new BearerOptions(),
        };
        var mode = AuthOptions.ModeFor(environment);
        auth.Validate(mode);

        services.AddAuthorization(options =>
            options.FallbackPolicy = new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build());

        if (mode == AuthOptions.AccessMode)
        {
            services.AddHttpClient(AccessKeys.HttpClientName, client => client.Timeout = TimeSpan.FromSeconds(10));
            services.AddSingleton(serviceProvider => new AccessKeys(
                serviceProvider.GetRequiredService<IHttpClientFactory>().CreateClient(AccessKeys.HttpClientName),
                auth.Access.Certs));
            services.AddAuthentication(AuthOptions.AccessMode).AddJwtBearer(AuthOptions.AccessMode);
            services.AddOptions<JwtBearerOptions>(AuthOptions.AccessMode)
                .Configure<AccessKeys>((options, keys) =>
                {
                    options.MapInboundClaims = false;
                    options.TokenValidationParameters = AccessTokenValidationParameters(auth.Access, keys);
                    options.Events = new JwtBearerEvents
                    {
                        OnTokenValidated = context =>
                        {
                            if (context.Principal?.Identity is ClaimsIdentity identity
                                && identity.AuthenticationType != AuthOptions.AccessMode)
                            {
                                context.Principal = new ClaimsPrincipal(
                                    new ClaimsIdentity(
                                        identity.Claims,
                                        AuthOptions.AccessMode,
                                        identity.NameClaimType,
                                        identity.RoleClaimType));
                            }

                            return Task.CompletedTask;
                        },
                        OnMessageReceived = context =>
                        {
                            if (context.Request.Headers.TryGetValue("Cf-Access-Jwt-Assertion", out var assertion)
                                && !StringValues.IsNullOrEmpty(assertion))
                            {
                                context.Token = assertion.ToString();
                            }

                            return Task.CompletedTask;
                        },
                        OnChallenge = context =>
                        {
                            context.HandleResponse();
                            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                            context.Response.Headers["WWW-Authenticate"] = "Bearer";
                            return Task.CompletedTask;
                        },
                    };
                });
        }
        else
        {
            services.AddAuthentication(AuthOptions.BearerMode)
                .AddScheme<BearerOptions, BearerHandler>(
                    AuthOptions.BearerMode,
                    options => configuration.GetSection("Auth:Bearer").Bind(options));
        }

        return services;
    }

    internal static IApplicationBuilder UseAuth(this IApplicationBuilder app)
    {
        app.UseAuthentication();
        app.UseAuthorization();
        app.UseMiddleware<IdentityLogMiddleware>();
        return app;
    }

    internal static TokenValidationParameters AccessTokenValidationParameters(AccessOptions access, AccessKeys keys) => new()
    {
        ValidIssuer = access.Issuer,
        ValidAudience = access.Audience,
        ValidateIssuer = true,
        ValidateAudience = true,
        ValidateIssuerSigningKey = true,
        ValidateLifetime = true,
        NameClaimType = "name",
        ValidAlgorithms = ["RS256"],
        IssuerSigningKeyResolver = (_, _, kid, _) => keys.KeysAsync(kid, CancellationToken.None).GetAwaiter().GetResult(),
    };
}
