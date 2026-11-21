using Librarian.Adapters;
using Librarian.Api.Features.Health;

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
        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        return services.AddPostgres(connectionString);
    }
}
