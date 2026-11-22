using Application.Handlers.Ingest.Extract;

namespace Tests.Ingest;

public sealed class FieldCatalogTests
{
    [Fact]
    public void Catalog_loads_with_all_kinds_and_their_fields()
    {
        var catalog = FieldCatalog.LoadDefault();
        Assert.Equal(8, catalog.Kinds.Count);
        Assert.Contains(catalog.Kinds, k => k.Name == "invoice" && k.Description.Contains("request to pay"));
        Assert.True(catalog.Fields.Count > 30);
        Assert.Equal("the company, office or person that issued the document.", catalog.Fields["issuer"]);
    }
}
