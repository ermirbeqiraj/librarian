namespace PostgresTests;

internal static class SolutionRoot
{
    internal static string Find()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "librarian.slnx")))
        {
            dir = dir.Parent;
        }

        return dir?.FullName
            ?? throw new InvalidOperationException("librarian.slnx not found above the test output.");
    }
}
