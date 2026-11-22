using Librarian.Application.Handlers.Ask;

namespace Librarian.Tests.Retrieve;

public sealed class SectionSearchTests
{
    private static string Words(int count, string word = "word")
        => string.Join(" ", Enumerable.Repeat(word, count)) + " ";

    [Fact]
    public void A_short_text_is_not_trimmed()
    {
        Assert.Equal(Words(100), SectionSearch.Trim(Words(100), "chunk", "query"));
        Assert.Equal(Words(300), SectionSearch.Trim(Words(300), "chunk", "query"));
    }

    [Fact]
    public void A_long_text_is_trimmed_around_the_query_term()
    {
        var text = Words(2000).Insert(Words(2000).Length - 5, "bolletta ");

        var trimmed = SectionSearch.Trim(text, null, "quanto costa la bolletta");

        Assert.True(trimmed.Length <= SectionSearch.TrimLimit + 2 * SectionSearch.TrimMarker.Length);
        Assert.Contains("bolletta", trimmed, StringComparison.Ordinal);
    }

    [Fact]
    public void The_anchor_matches_an_accented_term()
    {
        var text = Words(500) + "perché " + Words(500);

        Assert.Equal(2500, SectionSearch.Anchor(text, null, "perche"));
    }

    [Fact]
    public void Without_a_term_the_best_chunk_places_the_anchor()
    {
        var text = Words(1100) + "chunk " + Words(1100);

        var anchor = SectionSearch.Anchor(text, "header\nchunk", "zzz");

        Assert.InRange(anchor, 5500, 5506);
    }

    [Fact]
    public void With_nothing_to_anchor_on_the_middle_holds()
    {
        var text = Words(2000, "aaaa");

        Assert.Equal(5000, SectionSearch.Anchor(text, null, "zzz"));
    }

    [Fact]
    public void The_window_marks_both_cuts()
    {
        var trimmed = SectionSearch.Trim(Words(3000), null, "");

        Assert.StartsWith(SectionSearch.TrimMarker, trimmed);
        Assert.EndsWith(SectionSearch.TrimMarker, trimmed);
    }
}
