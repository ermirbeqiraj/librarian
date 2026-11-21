using Librarian.Application.Handlers.Ingest;
using Librarian.Application.Ports.Ingest;

namespace Librarian.Tests.Ingest;

public sealed class ReaderFailureTests
{
    [Fact]
    public void Null_or_empty_read_is_a_failure()
    {
        Assert.True(ReaderFailure.IsFailure(null, 200));
        Assert.True(ReaderFailure.IsFailure([], 200));
        Assert.True(ReaderFailure.IsFailure([new Page(1, "")], 200));
    }

    [Fact]
    public void Average_chars_per_page_below_the_minimum_is_a_failure()
    {
        var pages = new List<Page> { new(1, new string('x', 100)), new(2, new string('x', 100)) };
        Assert.True(ReaderFailure.IsFailure(pages, 200));
        Assert.False(ReaderFailure.IsFailure(pages, 100));
    }
}
