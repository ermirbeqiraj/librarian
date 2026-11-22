using Ingest;

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddIngestServices(builder.Configuration);

await builder.Build().RunAsync();
