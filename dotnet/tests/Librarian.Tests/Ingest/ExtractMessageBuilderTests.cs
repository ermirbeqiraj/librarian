using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Ports.Ingest;

namespace Librarian.Tests.Ingest;

public sealed class ExtractMessageBuilderTests
{
    private static readonly FieldCatalog Catalog = FieldCatalog.LoadDefault();
    private readonly ExtractMessageBuilder _builder = new(Catalog);

    private static List<Page> Pages(int count) => [.. Enumerable.Range(1, count).Select(n => new Page(n, $"text of page {n}"))];

    [Fact]
    public void Short_document_goes_whole_and_says_so()
    {
        var message = _builder.Build("doc.pdf", Pages(7), headPages: 5, tailPages: 5);
        Assert.Contains("has 7 page(s). All pages follow.", message);
        Assert.Contains("--- page 7 ---", message);
        Assert.DoesNotContain("left out", message);
    }

    [Fact]
    public void Long_document_keeps_head_and_tail_and_says_what_is_cut()
    {
        var message = _builder.Build("doc.pdf", Pages(20), headPages: 5, tailPages: 5);
        Assert.Contains("pages 1–5 and 16–20; the middle is left out", message);
        Assert.Contains("--- page 1 ---", message);
        Assert.Contains("--- page 5 ---", message);
        Assert.Contains("--- page 16 ---", message);
        Assert.Contains("--- page 20 ---", message);
        Assert.DoesNotContain("--- page 6 ---", message);
        Assert.DoesNotContain("--- page 15 ---", message);
    }

    [Fact]
    public void Message_carries_the_catalog()
    {
        var message = _builder.Build("doc.pdf", Pages(1), 5, 5);
        Assert.Contains("- invoice:", message);
        Assert.Contains("- issuer:", message);
    }

    [Fact]
    public void Select_boundary_exactly_head_plus_tail_goes_whole()
    {
        var selected = ExtractMessageBuilder.Select(Pages(10), 5, 5, out var cut);
        Assert.False(cut);
        Assert.Equal(10, selected.Count);
    }
}
