using Application.Domain;
using Application.Handlers.Ask;
using Microsoft.EntityFrameworkCore;

namespace Api;

public sealed class AskRetentionWorker(
    ILogger<AskRetentionWorker> logger,
    IServiceScopeFactory scopeFactory,
    AskRetentionOptions retention) : BackgroundService
{
    private readonly SemaphoreSlim scanLock = new(1, 1);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        logger.LogInformation("Ask retention started; asks older than {Days} days are deleted", retention.Days);
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(retention.ScanMinutes));
        try
        {
            do
            {
                if (!await scanLock.WaitAsync(0, stoppingToken))
                {
                    logger.LogDebug("The previous retention scan is still running; skipping this tick");
                    continue;
                }
                try
                {
                    await ScanAsync(stoppingToken);
                }
                finally
                {
                    scanLock.Release();
                }
            }
            while (await timer.WaitForNextTickAsync(stoppingToken));
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
    }

    private async Task ScanAsync(CancellationToken stoppingToken)
    {
        try
        {
            using var scope = scopeFactory.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
            var cutoff = DateTime.UtcNow.AddDays(-retention.Days);
            var old = await db.Asks.Where(a => a.CreatedAt < cutoff).Select(a => a.Id).ToListAsync(stoppingToken);
            if (old.Count == 0)
                return;
            var gone = await db.Asks.Where(a => a.CreatedAt < cutoff).ExecuteDeleteAsync(stoppingToken);
            await db.SaveChangesAsync(stoppingToken);
            logger.LogInformation("Ask retention deleted {Asks} ask(s) older than {Cutoff:yyyy-MM-dd} with their spans", gone, cutoff);
        }
        catch (Exception ex) when (ex is not OperationCanceledException || !stoppingToken.IsCancellationRequested)
        {
            logger.LogError(ex, "The retention scan failed: {Message}", ex.Message);
        }
    }
}
