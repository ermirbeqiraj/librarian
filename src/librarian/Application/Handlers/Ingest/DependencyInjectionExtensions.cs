using Microsoft.Extensions.DependencyInjection;

namespace Application.Handlers.Ingest;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddIngestHandler(this IServiceCollection services)
    {
        services.AddScoped<IngestHandler>();
        return services;
    }
}
