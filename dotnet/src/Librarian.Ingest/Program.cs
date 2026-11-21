using Librarian.Ingest;

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddHostedService<Worker>();

await builder.Build().RunAsync();
