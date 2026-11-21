using Librarian.Adapters;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;
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
        librarian.Validate();
        var ingest = configuration.GetSection("Ingest").Get<IngestOptions>() ?? new IngestOptions();
        var mistral = configuration.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();

        librarian.Validate();
        ingest.Validate();
        mistral.Validate();

        services.AddLibrarianAdapters(librarian, ingest, mistral);
        services.AddSingleton<IIngestHandler, IngestHandler>();
        services.AddHostedService<Worker>();
        return services;
    }

    private static IServiceCollection AddTracing(this IServiceCollection services)
    {
        services.AddOpenTelemetry().WithTracing(tracing => tracing
            .AddSource("Microsoft.Agents.AI", "Microsoft.Extensions.AI")
            .AddConsoleExporter());
        return services;
    }
}
