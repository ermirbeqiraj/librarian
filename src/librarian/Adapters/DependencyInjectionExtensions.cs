using Adapters.Docling;
using Adapters.FileSystem;
using Adapters.Mistral;
using Adapters.Postgres;
using Adapters.Tei;
using Application.Domain;
using Application.Handlers.Ingest;
using Application.Handlers.Ingest.Extract;
using Application.Handlers.Ask;
using Application.Handlers.Retrieve;
using Application.Handlers.Store;
using Application.Ports.Ask;
using Application.Ports.Ingest;
using Application.Ports.Retrieve;
using Application.Ports.Store;
using Microsoft.Agents.AI;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;

namespace Adapters;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddPostgres(this IServiceCollection services, string connectionString)
    {
        services.AddSingleton<IModelConfiguration, PostgresModelConfiguration>();
        services.AddDbContext<LibrarianDbContext>(options => options
            .UseNpgsql(connectionString, npgsql => npgsql.UseVector().MigrationsAssembly("Adapters")));
        return services;
    }

    public static IServiceCollection AddPostgresSearch(this IServiceCollection services)
    {
        services.AddScoped<IVectorSearch, PostgresVectorSearch>();
        services.AddScoped<IKeywordSearch, PostgresKeywordSearch>();
        return services;
    }

    public static IServiceCollection AddTei(this IServiceCollection services, StoreOptions store)
    {
        services.AddHttpClient("tei", client =>
            {
                client.BaseAddress = new Uri(store.Embedding.Url.TrimEnd('/') + "/");
                client.Timeout = Timeout.InfiniteTimeSpan;
            })
            .AddStandardResilienceHandler(options =>
            {
                options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(store.Embedding.TimeoutSeconds);
                options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(store.Embedding.TimeoutSeconds);
                options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(2 * store.Embedding.TimeoutSeconds);
                options.Retry.ShouldHandle = static _ => ValueTask.FromResult(false);
            });
        services.AddSingleton<ITokenCounter, TeiTokenCounter>();
        services.AddSingleton<IEmbeddingGenerator<string, Embedding<float>>, TeiEmbeddingGenerator>();
        return services;
    }

    public static IServiceCollection AddLibrarianAdapters(
        this IServiceCollection services, LibrarianOptions paths, IngestOptions ingest, MistralOptions mistral)
    {
        services.AddSingleton(paths);
        services.AddSingleton(ingest);
        services.AddSingleton(mistral);

        services.AddSingleton<IIngestFileStore, IngestFileStore>();
        services.AddSingleton<IOcrBudget, FileOcrBudget>();

        services.AddHttpClient("doclingReader", client =>
            {
                client.BaseAddress = new Uri(ingest.Docling.Url.TrimEnd('/') + "/");
                client.Timeout = Timeout.InfiniteTimeSpan;
            })
            .AddStandardResilienceHandler(options =>
            {
                options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(ingest.Docling.TimeoutSeconds);
                options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(ingest.Docling.TimeoutSeconds);
                options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(2 * ingest.Docling.TimeoutSeconds);
            });
        services.AddKeyedSingleton<IDocumentReader, DoclingReader>("doclingReader");

        services.AddHttpClient("ocrReader", client =>
            {
                client.BaseAddress = new Uri(ingest.Ocr.Url);
                client.Timeout = Timeout.InfiniteTimeSpan;
            })
            .AddStandardResilienceHandler(options =>
            {
                options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(ingest.Ocr.TimeoutSeconds);
                options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(ingest.Ocr.TimeoutSeconds);
                options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(2 * ingest.Ocr.TimeoutSeconds);
                options.Retry.ShouldHandle = static _ => ValueTask.FromResult(false);
            });
        services.AddKeyedSingleton<IDocumentReader, MistralOcrReader>("ocrReader");

        services.AddSingleton<IExtractRunOptionsFactory, ExtractRunOptionsFactory>();
        services.AddSingleton(_ => FieldCatalog.LoadDefault());
        services.AddSingleton<ExtractMessageBuilder>();
        services.AddKeyedSingleton<AIAgent>("extractAgent", (sp, _) => MistralAgentFactory.CreateExtractAgent(
            sp, mistral.ApiKey, ingest.Extract.BaseUrl, ingest.Extract.Model, ingest.Extract.ReasoningEffort, ingest.Extract.MaxRounds));

        return services;
    }

    public static IServiceCollection AddLibrarianRefine(
        this IServiceCollection services, MistralOptions mistral, RefineOptions refine)
    {
        services.AddSingleton(mistral);
        services.AddSingleton(refine);
        services.AddSingleton<IRefineRunOptionsFactory, RefineRunOptionsFactory>();
        services.AddKeyedSingleton<AIAgent>("refineAgent", (sp, _) =>
        {
            mistral.Validate();
            return MistralAgentFactory.CreateRefineAgent(sp, mistral.ApiKey, refine.BaseUrl, refine.Model);
        });
        return services;
    }

    public static IServiceCollection AddLibrarianAsk(
        this IServiceCollection services, MistralOptions mistral, AskOptions ask, string readerConnectionString)
    {
        services.AddSingleton(mistral);
        services.AddSingleton(ask);
        services.AddSingleton<ISql>(_ => new PostgresSql(readerConnectionString));
        services.AddSingleton<IAskRunOptionsFactory, AskRunOptionsFactory>();
        services.AddKeyedSingleton<IChatClient>("askChat", (sp, _) =>
        {
            mistral.Validate();
            return MistralAgentFactory.AskChat(mistral.ApiKey, ask.BaseUrl, ask.Model);
        });
        services.AddKeyedSingleton<AIAgent>("askAgent", (sp, _) =>
        {
            mistral.Validate();
            return MistralAgentFactory.CreateAskAgent(sp, sp.GetRequiredKeyedService<IChatClient>("askChat"), ask.ReasoningEffort, ask.MaxRounds);
        });
        return services;
    }
}

