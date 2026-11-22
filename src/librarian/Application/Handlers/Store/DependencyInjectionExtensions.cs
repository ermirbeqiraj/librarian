using Microsoft.Extensions.DependencyInjection;

namespace Application.Handlers.Store;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddStoreHandler(this IServiceCollection services)
    {
        services.AddScoped<StoreHandler>();
        return services;
    }
}
