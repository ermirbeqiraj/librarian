using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Application.Handlers.Retrieve;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddQueryRefiner(this IServiceCollection services)
    {
        services.AddSingleton<QueryRefiner>();
        return services;
    }
}
