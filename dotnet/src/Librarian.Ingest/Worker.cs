using Librarian.Application.Domain;
using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Librarian.Ingest;

public sealed class Worker(
    ILogger<Worker> logger,
    LibrarianOptions librarianOptions,
    IngestOptions ingestOptions,
    IIngestFileStore fileStore,
    IServiceScopeFactory scopeFactory) : BackgroundService
{
    private static readonly TimeSpan UnchangedFor = TimeSpan.FromSeconds(60);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        Directory.CreateDirectory(librarianOptions.InboxPath);
        logger.LogInformation("Ingest started; watching {Inbox}", librarianOptions.InboxPath);

        var interval = TimeSpan.FromSeconds(librarianOptions.ScanIntervalSeconds);
        var seen = new Dictionary<string, (long Size, DateTime LastWriteUtc)>();
        using var timer = new PeriodicTimer(interval);
        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                await ScanAsync(seen, stoppingToken);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
    }

    private async Task ScanAsync(Dictionary<string, (long Size, DateTime LastWriteUtc)> seen, CancellationToken stoppingToken)
    {
        string[] files;
        try
        {
            files = [.. Directory.EnumerateFiles(librarianOptions.InboxPath)];
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogError(ex, "Scanning the inbox failed: {Message}", ex.Message);
            return;
        }

        var now = DateTime.UtcNow;
        foreach (var path in files)
        {
            try
            {
                var info = new FileInfo(path);
                var state = (info.Length, info.LastWriteTimeUtc);
                if (seen.TryGetValue(path, out var previous)
                    && previous == state
                    && now - previous.LastWriteUtc >= UnchangedFor)
                {
                    seen.Remove(path);
                    using var scope = scopeFactory.CreateScope();
                    var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
                    var attempts = await db.Ingestions
                        .CountAsync(i => i.FileName == info.Name && i.FileSize == info.Length, stoppingToken);
                    if (attempts >= ingestOptions.MaxAttempts)
                    {
                        logger.LogWarning("Giving up on {File}: {Attempts} attempts are already banked", info.Name, attempts);
                        await fileStore.MoveToProcessedAsync(path, stoppingToken);
                        continue;
                    }
                    logger.LogInformation("Taking {File} ({Size} bytes)", info.Name, info.Length);
                    var handler = scope.ServiceProvider.GetRequiredService<IngestHandler>();
                    await handler.HandleAsync(new IngestFile(path, info.Name, info.Length), stoppingToken);
                }
                else
                {
                    seen[path] = state;
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException || !stoppingToken.IsCancellationRequested)
            {
                logger.LogError(ex, "Taking {File} failed: {Message}", Path.GetFileName(path), ex.Message);
            }
        }
    }
}
