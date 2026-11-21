using Librarian.Adapters;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Tests.Ingest;

public sealed class ReaderAdapterTests
{
    private static (ServiceProvider Provider, LibrarianOptions Paths) Build()
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(Path.Combine(FindSolutionRoot(), "src", "Librarian.Ingest"))
            .AddJsonFile("appsettings.json", optional: false)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddEnvironmentVariables()
            .Build();
        var paths = config.GetSection("Librarian").Get<LibrarianOptions>() ?? new LibrarianOptions();
        var ingest = config.GetSection("Ingest").Get<IngestOptions>() ?? new IngestOptions();
        var mistral = config.GetSection("Mistral").Get<MistralOptions>() ?? new MistralOptions();
        paths.Validate();
        ingest.Validate();
        mistral.Validate();
 var services = new ServiceCollection();
        services.AddLogging();
        services.AddLibrarianAdapters(paths, ingest, mistral);
        return (services.BuildServiceProvider(), paths);
    }

    [Fact]
    public async Task Docling_reads_a_document_to_markdown_pages()
    {
        var (provider, paths) = Build();
        await using var _ = provider.ConfigureAwait(false);
        var reader = provider.GetRequiredKeyedService<IDocumentReader>("doclingReader");
        var pages = await reader.ReadAsync(Document(paths), CancellationToken.None);
        Assert.NotEmpty(pages);
        Assert.All(pages, p => Assert.True(p.Number >= 1));
        Assert.True(pages.Sum(p => p.Markdown.Length) > 0);
    }

    [Fact]
    public async Task Mistral_ocr_reads_a_document_to_markdown_pages()
    {
        var (provider, paths) = Build();
        await using var _ = provider.ConfigureAwait(false);
        var reader = provider.GetRequiredKeyedService<IDocumentReader>("ocrReader");
        var pages = await reader.ReadAsync(Document(paths), CancellationToken.None);
        Assert.NotEmpty(pages);
        Assert.True(pages.Sum(p => p.Markdown.Length) > 0);
    }

    private static string Document(LibrarianOptions paths)
        => Directory.GetFiles(paths.DocumentsPath, "*.pdf").OrderBy(p => p, StringComparer.Ordinal).First();

    private static string FindSolutionRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "Librarian.slnx")))
            dir = dir.Parent;
        return dir?.FullName ?? throw new InvalidOperationException("Librarian.slnx not found above the test output.");
    }
}
