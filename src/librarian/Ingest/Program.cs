using Application.Domain;
using Ingest;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddIngestServices(builder.Configuration);

var host = builder.Build();

// The app owns its schema: on start, any pending migrations run as the owner login.
using (var scope = host.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<LibrarianDbContext>();
    await db.Database.MigrateAsync();
}

await host.RunAsync();
