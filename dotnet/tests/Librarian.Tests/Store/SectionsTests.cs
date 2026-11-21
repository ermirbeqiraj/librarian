using Librarian.Application.Handlers.Store;

namespace Librarian.Tests.Store;

public sealed class SectionsTests
{
    [Fact]
    public void A_markdown_line_with_hashes_opens_a_section()
    {
        var sections = Sections.FromMarkdown("# Invoice\n\nACME\n\n# Details\n\nTotal 10\n");
        Assert.Equal(2, sections.Count);
        Assert.Equal(("Invoice", "ACME"), sections[0]);
        Assert.Equal(("Details", "Total 10"), sections[1]);
    }

    [Fact]
    public void A_repeated_heading_does_not_open_a_new_section()
    {
        var sections = Sections.FromMarkdown("# A\n\none\n\n# A\n\ntwo\n");
        var section = Assert.Single(sections);
        Assert.Equal("A", section.Heading);
        Assert.Equal("one\n\n# A\n\ntwo", section.Text);
    }

    [Fact]
    public void A_document_without_headings_is_one_section()
    {
        var sections = Sections.FromMarkdown("just\n\ntext\n");
        var section = Assert.Single(sections);
        Assert.Equal("", section.Heading);
        Assert.Equal("just\n\ntext", section.Text);
    }

    [Fact]
    public void Image_lines_are_dropped()
    {
        var sections = Sections.FromMarkdown("# A\n\n![alt](img.png)\n\ntext\n");
        var section = Assert.Single(sections);
        Assert.Equal("text", section.Text);
    }
}
