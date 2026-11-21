using Librarian.Adapters;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Handlers.Store;
using OpenTelemetry.Trace;

namespace Librarian.Ingest;

public static class ProgramExtensions
{
    public static IServiceCollection AddIngestServices(this IServiceCollection services, IConfiguration configuration)
    {
        AddOptions(services, configuration);
        AddTracing(services);
        return services;
    }

    private static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
    {
        var librarian = configuration.GetSection("Librarian").Get<LibrarianOptions>() ?? new LibrarianOptions();
        var ingest = configuration.GetSection("Ingest").Get<IngestOptions>() ?? new IngestOptions();
        var mistral = configuration.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();
        var store = configuration.GetSection("Store").Get<StoreOptions>() ?? new StoreOptions();

        librarian.Validate();
        ingest.Validate();
        mistral.Validate();
        store.Validate();

        services.AddLibrarianAdapters(librarian, ingest, mistral);
        services.AddSingleton(store);
        services.AddIngestHandler();
        services.AddStoreHandler();
        AddDb(services, configuration);
        services.AddTei(store);
        services.AddHostedService<Worker>();
        services.AddHostedService<StoreWorker>();
        return services;
    }

    private static IServiceCollection AddDb(this IServiceCollection services, IConfiguration configuration)
    {
        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        return services.AddPostgres(connectionString);
    }

    private static IServiceCollection AddTracing(this IServiceCollection services)
    {
        services.AddOpenTelemetry().WithTracing(tracing => tracing
            .AddSource("Microsoft.Agents.AI", "Microsoft.Extensions.AI")
            .AddConsoleExporter());
        return services;
    }
}
