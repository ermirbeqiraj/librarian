using Librarian.Adapters.Postgres;
using Librarian.Api.Features.Health;
using Microsoft.EntityFrameworkCore;

namespace Librarian.Api;

public static class ProgramExtensions
{
    public static IServiceCollection AddApiServices(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddDb(configuration);
        return services;
    }

    public static WebApplication MapApiEndpoints(this WebApplication app)
    {
        app.MapHealthEndpoints();
        return app;
    }

    private static IServiceCollection AddDb(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddDbContext<LibrarianDbContext>(options =>
            options.UseNpgsql(configuration.GetConnectionString("Postgres")));
        return services;
    }
}
