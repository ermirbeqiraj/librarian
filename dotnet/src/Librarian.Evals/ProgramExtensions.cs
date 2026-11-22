using Librarian.Adapters;
using Librarian.Application.Handlers.Store;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;

namespace Librarian.Evals;

public static class ProgramExtensions
{
    public static IServiceCollection AddEvalsServices(this IServiceCollection services, IConfiguration configuration)
    {
        var store = configuration.GetSection("Store").Get<StoreOptions>() ?? new StoreOptions();
        store.Validate();
        var evals = configuration.GetSection("Evals").Get<EvalsOptions>() ?? new EvalsOptions();
        evals.Validate();

        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        RequireLocalDatabase(connectionString);

        services.AddPostgres(connectionString);
        services.AddSingleton(store);
        services.AddSingleton(evals);
        services.AddTei(store);
        return services;
    }

    private static void RequireLocalDatabase(string connectionString)
    {
        var settings = new NpgsqlConnectionStringBuilder(connectionString);
        var local = string.IsNullOrWhiteSpace(settings.Host)
            || settings.Host is "localhost" or "127.0.0.1" or "::1";
        if (!local)
            throw new InvalidOperationException(
                $"The evals runner works only on a local database; Host={settings.Host}.");
    }
}
