using Application.Domain;
using Microsoft.EntityFrameworkCore;

namespace Adapters.Postgres;

public sealed class PostgresModelConfiguration : IModelConfiguration
{
    public void Configure(ModelBuilder modelBuilder)
        => modelBuilder.ApplyConfigurationsFromAssembly(typeof(PostgresModelConfiguration).Assembly);
}
