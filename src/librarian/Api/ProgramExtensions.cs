using Adapters;
using Api.Features.Auth;
using Api.Features.Health;
using Api.Features.Whoami;
using Application.Handlers.Ask;
using Microsoft.Extensions.Hosting;

namespace Api;

public static class ProgramExtensions
{
    public static IServiceCollection AddApiServices(
        this IServiceCollection services,
        IConfiguration configuration,
        IHostEnvironment environment)
    {
        services.AddDb(configuration);
        AddRetention(services, configuration);
        services.AddAuth(configuration, environment);
        return services;
    }

    private static void AddRetention(IServiceCollection services, IConfiguration configuration)
    {
        var retention = configuration.GetSection("Ask:Retention").Get<AskRetentionOptions>() ?? new AskRetentionOptions();
        retention.Validate();
        services.AddSingleton(retention);
        services.AddHostedService<AskRetentionWorker>();
    }

    public static WebApplication MapApiEndpoints(this WebApplication app)
    {
        app.MapHealthEndpoints();
        app.MapWhoamiEndpoints();
        return app;
    }

    private static IServiceCollection AddDb(this IServiceCollection services, IConfiguration configuration)
    {
        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        return services.AddPostgres(connectionString);
    }
}
