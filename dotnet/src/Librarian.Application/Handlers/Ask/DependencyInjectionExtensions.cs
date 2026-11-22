using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Application.Handlers.Ask;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddAskHandler(this IServiceCollection services)
    {
        services.AddScoped<SectionSearch>();
        services.AddScoped<AskHandler>();
        return services;
    }
}
