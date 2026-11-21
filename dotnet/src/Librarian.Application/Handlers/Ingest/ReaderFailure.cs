using Librarian.Application.Ports.Ingest;

namespace Librarian.Application.Handlers.Ingest;

public static class ReaderFailure
{
    public static bool IsFailure(IReadOnlyList<Page>? pages, int minCharsPerPage)
    {
        if (pages is null || pages.Count == 0)
            return true;
        var characters = pages.Sum(p => p.Markdown.Length);
        return characters == 0 || characters / pages.Count < minCharsPerPage;
    }
}
