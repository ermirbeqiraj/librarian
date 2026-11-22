using Librarian.Evals;
using Librarian.Evals.Refine;
using Librarian.Evals.Search;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    ContentRootPath = AppContext.BaseDirectory,
});

builder.Services.AddEvalsServices(builder.Configuration);

using var host = builder.Build();

if (args.Length == 0)
{
    return Usage();
}

return args[0] switch
{
    "search" => await SearchCommand.RunAsync(host.Services, args[1..]),
    "refine" => await RefineCommand.RunAsync(host.Services, args[1..]),
    _ => Usage(),
};

static int Usage()
{
    Console.Error.WriteLine("usage: Librarian.Evals <command> [options]");
    Console.Error.WriteLine("commands: search, refine");
    return 2;
}
