using Adapters;
using Adapters.Postgres;
using Application.Handlers.Ask;
using Application.Handlers.Ingest;
using Application.Handlers.Retrieve;
using Application.Handlers.Store;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace Evals;

public static class ProgramExtensions
{
    public static IServiceCollection AddEvalsServices(this IServiceCollection services, IConfiguration configuration)
    {
        var store = configuration.GetSection("Store").Get<StoreOptions>() ?? new StoreOptions();
        store.Validate();
        var evals = configuration.GetSection("Evals").Get<EvalsOptions>() ?? new EvalsOptions();
        evals.Validate();
        var refine = configuration.GetSection("Refine").Get<RefineOptions>() ?? new RefineOptions();
        refine.Validate();
        var mistral = configuration.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();
        var paths = configuration.GetSection("Librarian").Get<LibrarianOptions>() ?? new LibrarianOptions();
        paths.Validate();
        var ask = configuration.GetSection("Ask").Get<AskOptions>() ?? new AskOptions();
        ask.Validate();

        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        var readerConnectionString = configuration.GetConnectionString("PostgresReader")
            ?? throw new InvalidOperationException("ConnectionStrings:PostgresReader is not set.");
        RequireLocalDatabase(connectionString);
        RequireLocalDatabase(readerConnectionString);

        services.AddPostgres(connectionString).AddPostgresSearch();
        services.AddSingleton(store);
        services.AddSingleton(evals);
        services.AddSingleton(paths);
        services.AddTei(store);
        services.AddLibrarianRefine(mistral, refine);
        services.AddQueryRefiner();
        services.AddLibrarianAsk(mistral, ask, readerConnectionString);
        services.AddAskHandler();
        services.AddOpenTelemetry()
            .ConfigureResource(resource => resource.AddService("Evals"))
            .WithTracing(tracing => tracing
            .AddSource("Microsoft.Agents.AI", "Microsoft.Extensions.AI", AskTrace.SourceName)
            .AddProcessor(_ => new AskSpanProcessor(connectionString))
            // The live view: traces stream to the compose aspire dashboard while the eval runs.
            .AddOtlpExporter(exporter =>
            {
                // The eval runs on the host; the dashboard's ingest port is published there.
                exporter.Endpoint = new Uri(configuration["Aspire:Endpoint"] ?? "http://127.0.0.1:18889");
            }));
        return services;
    }

    private static void RequireLocalDatabase(string connectionString)
    {
        var settings = new NpgsqlConnectionStringBuilder(connectionString);
        var local = string.IsNullOrWhiteSpace(settings.Host)
            || settings.Host is "localhost" or "127.0.0.1" or "::1";
        if (!local)
            throw new InvalidOperationException(
                $"The evals runner works only on a local database; Host={settings.Host}.");
    }
}
