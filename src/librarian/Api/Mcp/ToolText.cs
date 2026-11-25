using Application.Handlers.Ingest;

namespace Api.Mcp;

internal static class ToolText
{
    internal static string ServerInstructions(LibrarianOptions paths)
    {
        var path = Path.Combine(paths.InstructionsPath, "server.md");
        if (!File.Exists(path))
            throw new InvalidOperationException($"The server instructions are missing: {path}.");
        return File.ReadAllText(path).Trim();
    }
}
