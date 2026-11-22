using Evals;
using Evals.Refine;
using Evals.Retrieval;
using Evals.Search;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddEvalsServices(builder.Configuration);

using var host = builder.Build();
await host.StartAsync();

if (args.Length == 0)
{
    return Usage();
}

return args[0] switch
{
    "search" => await SearchCommand.RunAsync(host.Services, args[1..]),
    "refine" => await RefineCommand.RunAsync(host.Services, args[1..]),
    "retrieval" => await RetrieveCommand.RunAsync(host.Services, args[1..]),
    _ => Usage(),
};

static int Usage()
{
    Console.Error.WriteLine("usage: Evals <command> [options]");
    Console.Error.WriteLine("commands: search, refine, retrieval");
    return 2;
}
