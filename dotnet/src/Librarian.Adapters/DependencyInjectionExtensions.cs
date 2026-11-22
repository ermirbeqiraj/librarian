using Librarian.Adapters.Docling;
using Librarian.Adapters.FileSystem;
using Librarian.Adapters.Mistral;
using Librarian.Adapters.Postgres;
using Librarian.Adapters.Tei;
using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Handlers.Store;
using Librarian.Application.Ports.Ingest;
using Librarian.Application.Ports.Retrieve;
using Librarian.Application.Ports.Store;
using Microsoft.Agents.AI;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Adapters;

public static class DependencyInjectionExtensions
{
    public static IServiceCollection AddPostgres(this IServiceCollection services, string connectionString)
    {
        services.AddSingleton<IModelConfiguration, PostgresModelConfiguration>();
        services.AddDbContext<LibrarianDbContext>(options => options
            .UseNpgsql(connectionString, npgsql => npgsql.UseVector().MigrationsAssembly("Librarian.Adapters")));
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
        services.AddKeyedSingleton<AIAgent>("extractAgent", (sp, _) => MistralAgentFactory.Create(
            sp, mistral.ApiKey, ingest.Extract.BaseUrl, ingest.Extract.Model, ingest.Extract.ReasoningEffort, ingest.Extract.MaxRounds));

        return services;
    }
}
