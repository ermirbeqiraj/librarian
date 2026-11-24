using Adapters;
using Api.Features.Auth;
using Api.Features.Health;
using Api.Features.Whoami;
using Api.Mcp;
using Api.Mcp.Ask;
using Api.Mcp.GetDocument;
using Api.Mcp.GetSection;
using Api.Mcp.Library;
using Application.Domain;
using Application.Handlers.Ask;
using Application.Handlers.Ingest;
using Application.Handlers.Retrieve;
using Application.Handlers.Serve;
using Application.Handlers.Store;
using Microsoft.Extensions.Hosting;
using ModelContextProtocol.Server;

namespace Api;

public static class ProgramExtensions
{
    public static IServiceCollection AddApiServices(
        this IServiceCollection services,
        IConfiguration configuration,
        IHostEnvironment environment)
    {
        services.AddDb(configuration);
        AddRetention(services, configuration);
        services.AddAuth(configuration, environment);
        var paths = configuration.GetSection("Librarian").Get<LibrarianOptions>() ?? new LibrarianOptions();
        paths.Validate();
        AddAsk(services, configuration, paths);
        AddMcp(services, paths);
        return services;
    }

    private static void AddRetention(IServiceCollection services, IConfiguration configuration)
    {
        var retention = configuration.GetSection("Ask:Retention").Get<AskRetentionOptions>()
            ?? new AskRetentionOptions();
        retention.Validate();
        services.AddSingleton(retention);
        services.AddHostedService<AskRetentionWorker>();
    }

    private static IServiceCollection AddAsk(IServiceCollection services, IConfiguration configuration, LibrarianOptions paths)
    {
        var store = configuration.GetSection("Store").Get<StoreOptions>() ?? new StoreOptions();
        store.Validate();
        var refine = configuration.GetSection("Refine").Get<RefineOptions>() ?? new RefineOptions();
        refine.Validate();
        var mistral = configuration.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();
        var ask = configuration.GetSection("Ask").Get<AskOptions>() ?? new AskOptions();
        ask.Validate();
        var readerConnectionString = configuration.GetConnectionString("PostgresReader")
            ?? throw new InvalidOperationException("ConnectionStrings:PostgresReader is not set.");

        services.AddSingleton(paths);
        services.AddSingleton(store);
        services.AddPostgresSearch();
        services.AddTei(store);
        services.AddLibrarianRefine(paths, mistral, refine);
        services.AddQueryRefiner();
        services.AddLibrarianAsk(mistral, ask, readerConnectionString);
        services.AddAskHandler();
        services.AddServeHandler();
        return services;
    }

    private static IServiceCollection AddMcp(IServiceCollection services, LibrarianOptions paths)
    {
        services.AddMcpServer(options => options.ServerInstructions = Mcp.ToolText.ServerInstructions(paths))
            .WithRequestFilters(filters => filters.AddCallToolFilter(next => async (request, cancellationToken) =>
            {
                try
                {
                    return await next(request, cancellationToken);
                }
                catch (DomainException ex)
                {
                    return Mcp.Results.Error(ex.Message);
                }
            }))
            .WithHttpTransport()
            .WithTools<AskTool>()
            .WithTools<GetSectionTool>()
            .WithTools<GetDocumentTool>()
            .WithTools<LibraryTool>();
        return services;
    }

    public static WebApplication MapApiEndpoints(this WebApplication app)
    {
        app.MapHealthEndpoints();
        app.MapWhoamiEndpoints();
        app.MapMcp("/mcp");
        return app;
    }

    private static IServiceCollection AddDb(this IServiceCollection services, IConfiguration configuration)
    {
        var connectionString = configuration.GetConnectionString("Postgres")
            ?? throw new InvalidOperationException("ConnectionStrings:Postgres is not set.");
        return services.AddPostgres(connectionString);
    }
}
