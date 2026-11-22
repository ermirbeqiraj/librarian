using Application.Domain;
using Application.Handlers.Store;
using Microsoft.EntityFrameworkCore;

namespace Ingest;

public sealed class StoreWorker(
    ILogger<StoreWorker> logger,
    IServiceScopeFactory scopeFactory,
    StoreOptions storeOptions) : BackgroundService
{
    private readonly SemaphoreSlim _scanLock = new(1, 1);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        logger.LogInformation("Store started; scanning every {Seconds}s", storeOptions.ScanIntervalSeconds);
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(storeOptions.ScanIntervalSeconds));
        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                if (!await _scanLock.WaitAsync(0, stoppingToken))
                {
                    logger.LogDebug("The previous store scan is still running; skipping this tick");
                    continue;
                }
                try
                {
                    await ScanAsync(stoppingToken);
                }
                finally
                {
                    _scanLock.Release();
                }
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
    }

    private async Task ScanAsync(CancellationToken stoppingToken)
    {
        try
        {
            var lastId = 0L;
            while (true)
            {
                long? id;
                using (var scope = scopeFactory.CreateScope())
                {
                    var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
                    id = await db.Ingestions
                        .Where(i => i.Id > lastId
                            && (i.State == IngestionState.Extracted
                                || (i.State == IngestionState.Error
                                    && (i.ErrorReason == IngestionErrorReason.EmbedFailed || i.ErrorReason == IngestionErrorReason.SaveFailed)
                                    && i.Tries < storeOptions.MaxTries)))
                        .OrderBy(i => i.Id)
                        .Select(i => (long?)i.Id)
                        .FirstOrDefaultAsync(stoppingToken);
                }
                if (id is null)
                    return;
                lastId = id.Value;

                try
                {
                    using var scope = scopeFactory.CreateScope();
                    var handler = scope.ServiceProvider.GetRequiredService<StoreHandler>();
                    await handler.HandleAsync(id.Value, stoppingToken);
                }
                catch (Exception ex) when (ex is not OperationCanceledException || !stoppingToken.IsCancellationRequested)
                {
                    logger.LogError(ex, "Storing ingestion {IngestionId} failed: {Message}", id.Value, ex.Message);
                }
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException || !stoppingToken.IsCancellationRequested)
        {
            logger.LogError(ex, "The store scan failed: {Message}", ex.Message);
        }
    }
}
