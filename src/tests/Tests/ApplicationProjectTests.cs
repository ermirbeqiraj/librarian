using System.Reflection;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Tests;

public sealed class ApplicationProjectTests
{
    private static readonly Regex VendorPackage = new(
        @"Npgsql|Pgvector|Pomelo|SqlClient|Dapper|OpenAI",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    // Every other project of the solution, by assembly name — Application may reference none.
    private static readonly string[] SiblingProjects = ["Adapters", "Api", "Evals", "Ingest"];

    [Fact]
    public void Application_references_only_abstractions_no_vendor_package_and_no_other_solution_project()
    {
        var csproj = Path.Combine(FindSolutionRoot(), "librarian", "Application", "Application.csproj");
        var doc = XDocument.Load(csproj);
        XNamespace ns = doc.Root?.Name.Namespace ?? throw new InvalidOperationException("the csproj has no root element.");

        Assert.True(File.Exists(csproj));
        Assert.Empty(doc.Descendants(ns + "ProjectReference"));

        var vendorPackages = doc.Descendants(ns + "PackageReference")
            .Select(p => (string?)p.Attribute("Include") ?? string.Empty)
            .Where(id => VendorPackage.IsMatch(id))
            .ToList();
        Assert.Empty(vendorPackages);

        var assembly = Assembly.Load("Application");
        var references = assembly.GetReferencedAssemblies().Select(r => r.Name ?? string.Empty).ToList();
        Assert.DoesNotContain(references, name => SiblingProjects.Contains(name));
        Assert.DoesNotContain(references, name => VendorPackage.IsMatch(name));
        Assert.DoesNotContain(references, name => name.StartsWith("Microsoft.EntityFrameworkCore.", StringComparison.Ordinal));
    }

    internal static string FindSolutionRoot()
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
