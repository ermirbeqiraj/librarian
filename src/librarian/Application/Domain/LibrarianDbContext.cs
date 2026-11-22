using Microsoft.EntityFrameworkCore;

namespace Application.Domain;

public sealed class LibrarianDbContext(
    DbContextOptions<LibrarianDbContext> options,
    IEnumerable<IModelConfiguration> modelConfigurations) : DbContext(options)
{
    public DbSet<Ingestion> Ingestions => Set<Ingestion>();
    public DbSet<Document> Documents => Set<Document>();
    public DbSet<Ask> Asks => Set<Ask>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        foreach (var configuration in modelConfigurations)
            configuration.Configure(modelBuilder);
    }
}
