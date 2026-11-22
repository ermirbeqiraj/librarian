using System.Text;
using Application.Ports.Ingest;

namespace Application.Handlers.Ingest.Extract;

public sealed class ExtractMessageBuilder(FieldCatalog catalog)
{
    public string Build(string fileName, IReadOnlyList<Page> pages, int headPages, int tailPages)
    {
        var sb = new StringBuilder();
        sb.AppendLine("Catalog:");
        sb.AppendLine(catalog.ToMessageText());
        sb.AppendLine();
        sb.Append($"Document {fileName} has {pages.Count} page(s).");
        var selected = Select(pages, headPages, tailPages, out var cut);
        if (cut)
            sb.Append($" These are pages 1–{headPages} and {pages.Count - tailPages + 1}–{pages.Count}; the middle is left out.");
        else
            sb.Append(" All pages follow.");
        foreach (var page in selected)
        {
            sb.AppendLine();
            sb.AppendLine();
            sb.AppendLine($"--- page {page.Number} ---");
            sb.AppendLine(page.Markdown);
        }
        return sb.ToString();
    }

    public static IReadOnlyList<Page> Select(IReadOnlyList<Page> pages, int headPages, int tailPages, out bool cut)
    {
        if (pages.Count <= headPages + tailPages)
        {
            cut = false;
            return pages;
        }
        cut = true;
        return pages.Take(headPages).Concat(pages.TakeLast(tailPages)).ToList();
    }
}
