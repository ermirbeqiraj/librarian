namespace Librarian.PostgresTests;

internal static class SolutionRoot
{
    internal static string Find()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "Librarian.slnx")))
        {
            dir = dir.Parent;
        }

        return dir?.FullName
            ?? throw new InvalidOperationException("Librarian.slnx not found above the test output.");
    }
}
