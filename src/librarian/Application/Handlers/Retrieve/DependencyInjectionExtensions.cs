using Microsoft.Extensions.DependencyInjection;

namespace Application.Handlers.Retrieve;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddQueryRefiner(this IServiceCollection services)
    {
        services.AddSingleton<QueryRefiner>();
        return services;
    }
}
