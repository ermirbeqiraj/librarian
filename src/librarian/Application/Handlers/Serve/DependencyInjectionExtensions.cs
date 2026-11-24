using Microsoft.Extensions.DependencyInjection;

namespace Application.Handlers.Serve;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddServeHandler(this IServiceCollection services)
    {
        services.AddScoped<ServeHandler>();
        return services;
    }
}
