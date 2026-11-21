using System.Reflection;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Librarian.Tests;

public sealed class ApplicationProjectTests
{
    private static readonly Regex DatabasePackage = new(
        @"EntityFrameworkCore|Npgsql|Pomelo|SqlClient|Dapper",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    [Fact]
    public void Application_references_no_other_librarian_project_and_no_database_package()
    {
        var csproj = Path.Combine(FindSolutionRoot(), "src", "Librarian.Application", "Librarian.Application.csproj");
        var doc = XDocument.Load(csproj);
        XNamespace ns = doc.Root?.Name.Namespace ?? throw new InvalidOperationException("the csproj has no root element.");

        Assert.True(File.Exists(csproj));
        Assert.Empty(doc.Descendants(ns + "ProjectReference"));

        var databasePackages = doc.Descendants(ns + "PackageReference")
            .Select(p => (string?)p.Attribute("Include") ?? string.Empty)
            .Where(id => DatabasePackage.IsMatch(id))
            .ToList();
        Assert.Empty(databasePackages);

        var assembly = Assembly.Load("Librarian.Application");
        var references = assembly.GetReferencedAssemblies().Select(r => r.Name ?? string.Empty).ToList();
        Assert.DoesNotContain(references, name => name.StartsWith("Librarian.", StringComparison.Ordinal));
        Assert.DoesNotContain(references, name => DatabasePackage.IsMatch(name));
    }

    private static string FindSolutionRoot()
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
