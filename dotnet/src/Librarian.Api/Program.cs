using Librarian.Api;

var builder = WebApplication.CreateBuilder(new WebApplicationOptions
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddApiServices(builder.Configuration);

var app = builder.Build();

foreach (var url in app.Urls)
{
    app.Logger.LogInformation("Listening on {Url}; health at {Url}/health", url, url);
}

app.MapApiEndpoints();

app.Run();
