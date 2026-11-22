using System.Reflection;
using System.Text;
using System.Text.Json;

namespace Application.Handlers.Ingest.Extract;

public sealed class FieldCatalog
{
    public sealed record KindEntry(string Name, string Description);

    public sealed record CatalogFile(List<KindEntry> Kinds, Dictionary<string, string> Fields);

    public IReadOnlyList<KindEntry> Kinds { get; }
    public IReadOnlyDictionary<string, string> Fields { get; }

    private FieldCatalog(CatalogFile file)
    {
        Kinds = file.Kinds;
        Fields = file.Fields;
    }

    public static FieldCatalog LoadDefault()
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("Application.Handlers.Ingest.Extract.catalog.json")
            ?? throw new InvalidOperationException("catalog.json is not an embedded resource of Application.");
        var file = JsonSerializer.Deserialize<CatalogFile>(stream, ExtractJson.Options)
            ?? throw new InvalidOperationException("catalog.json is empty.");
        return new FieldCatalog(file);
    }

    public string ToMessageText()
    {
        var sb = new StringBuilder();
        sb.AppendLine("Kinds:");
        foreach (var kind in Kinds)
            sb.AppendLine($"- {kind.Name}: {kind.Description}");
        sb.AppendLine();
        sb.AppendLine("Field names, one per fact, with what each is:");
        foreach (var (name, description) in Fields)
            sb.AppendLine($"- {name}: {description}");
        sb.AppendLine();
        sb.AppendLine("The kinds are as described, the facts are as named: when the document states a fact, use exactly the name above; name anything else freely.");
        sb.AppendLine("The base fields issuer and issued_on are expected on every kind.");
        return sb.ToString();
    }
}
