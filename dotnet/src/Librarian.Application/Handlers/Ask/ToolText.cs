namespace Librarian.Application.Handlers.Ask;

public static class ToolText
{
    public static string Sql()
        => Resource("sql");

    public static string KeywordSearch()
        => Resource("keyword_search");

    public static string VectorSearch()
        => Resource("vector_search");

    public static string Submit()
        => Resource("submit");

    private static string Resource(string tool)
    {
        var assembly = typeof(ToolText).Assembly;
        using var stream = assembly.GetManifestResourceStream($"Librarian.Application.Handlers.Ask.ToolDescriptions.{tool}.md")
            ?? throw new InvalidOperationException($"{tool}.md is not an embedded resource of Librarian.Application.");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd().Trim();
    }
}
