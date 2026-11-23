using Api;
using Api.Features.Auth;

var builder = WebApplication.CreateBuilder(new WebApplicationOptions
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddApiServices(builder.Configuration, builder.Environment);

var app = builder.Build();

foreach (var url in app.Urls)
{
    app.Logger.LogInformation("Listening on {Url}; health at {Url}/health", url, url);
}

app.UseAuth();

app.MapApiEndpoints();

app.Run();
