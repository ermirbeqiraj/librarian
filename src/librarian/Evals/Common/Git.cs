using System.Diagnostics;

namespace Evals.Common;

internal static class Git
{
    public static string FindSha()
    {
        var directory = new DirectoryInfo(Directory.GetCurrentDirectory());
        while (directory is not null)
        {
            if (directory.EnumerateDirectories(".git").Any())
                return Sha(directory.FullName);
            directory = directory.Parent;
        }
        return "unknown";
    }

    private static string Sha(string repository)
    {
        using var process = Process.Start(new ProcessStartInfo
        {
            FileName = "git",
            Arguments = $"-C {repository} rev-parse HEAD",
            RedirectStandardOutput = true,
            UseShellExecute = false,
        });
        var sha = process?.StandardOutput.ReadToEnd().Trim();
        return string.IsNullOrEmpty(sha) ? "unknown" : sha!;
    }
}
