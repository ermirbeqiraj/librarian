namespace Librarian.Ingest;

/// <summary>
/// Scans the inbox on a timer and logs each tick, so the run is visible. The inbox is mounted only
/// into this program; the Api never sees the file system. The scan itself comes with task 03.
/// </summary>
public sealed class Worker(ILogger<Worker> logger, IConfiguration configuration) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var root = configuration["Librarian:Root"]
            ?? throw new InvalidOperationException("Librarian:Root is not configured (appsettings or env var Librarian__Root).");
        var inbox = Path.Combine(root, "inbox");
        Directory.CreateDirectory(inbox);
        logger.LogInformation("Ingest started; watching {Inbox}", inbox);

        var interval = TimeSpan.FromSeconds(configuration.GetValue("Librarian:ScanIntervalSeconds", 30));
        using var timer = new PeriodicTimer(interval);
        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                logger.LogInformation("Inbox scan tick at {Time:o}", DateTimeOffset.UtcNow);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            // Normal shutdown.
        }
    }
}
