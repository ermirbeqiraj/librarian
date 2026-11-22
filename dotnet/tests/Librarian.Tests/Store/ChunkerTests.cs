using Librarian.Application.Handlers.Store;

namespace Librarian.Tests.Store;

public sealed class ChunkerTests
{
    private static Chunker Words(int budget)
        => new(budget, (text, _) => Task.FromResult(text.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length));

    [Fact]
    public async Task A_section_within_the_budget_is_one_chunk_with_the_header()
    {
        var chunker = Words(100);
        var chunks = await chunker.ChunkAsync("invoice — ACME", "one two three", TestContext.Current.CancellationToken);
        var chunk = Assert.Single(chunks);
        Assert.Equal("invoice — ACME\none two three", chunk);
    }

    [Fact]
    public async Task Paragraphs_are_grouped_until_the_budget_and_split_at_paragraph_breaks()
    {
        var chunker = Words(10);
        var text = string.Join("\n\n", Enumerable.Range(1, 6).Select(i => $"p{i} " + string.Join(" ", Enumerable.Repeat("w", 3))));
        var chunks = await chunker.ChunkAsync("h", text, TestContext.Current.CancellationToken);
        Assert.True(chunks.Count > 1);
        Assert.All(chunks, c => Assert.StartsWith("h\n", c));
        Assert.All(chunks, c => Assert.True(c.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= 10));
        Assert.Equal(text.Replace("\n\n", " "), string.Join(" ", chunks.Select(c => c["h\n".Length..])));
    }

    [Fact]
    public async Task A_paragraph_over_the_budget_is_cut_at_sentence_then_word_breaks()
    {
        var chunker = Words(6);
        var chunks = await chunker.ChunkAsync("h", "aaa bbb. ccc ddd, eee fff. ggg hhh.", TestContext.Current.CancellationToken);
        Assert.True(chunks.Count > 1);
        Assert.All(chunks, c => Assert.True(c.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= 6));
    }

    [Fact]
    public async Task A_table_within_the_budget_sits_whole_in_one_chunk()
    {
        var chunker = Words(100);
        var table = "| h1 | h2 |\n| --- | --- |\n| a | b |\n| c | d |";
        var chunks = await chunker.ChunkAsync("h", table, TestContext.Current.CancellationToken);
        var chunk = Assert.Single(chunks);
        Assert.Equal("h\n" + table, chunk);
    }

    [Fact]
    public async Task An_oversized_table_splits_at_rows_and_repeats_the_header_in_every_chunk()
    {
        var chunker = Words(16);
        var table = "| h1 | h2 |\n| --- | --- |\n| a | b |\n| c | d |\n| e | f |";
        var chunks = await chunker.ChunkAsync("h", table, TestContext.Current.CancellationToken);
        Assert.True(chunks.Count > 1);
        Assert.All(chunks, c => Assert.Contains("| h1 | h2 |", c));
        Assert.All(chunks, c => Assert.Contains("| --- | --- |", c));
        Assert.Contains("| a | b |", chunks[0]);
        Assert.DoesNotContain("| c | d |", chunks[0]);
        Assert.Contains("| c | d |", chunks[1]);
        Assert.All(chunks, c => Assert.True(c.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= 16));
    }

    [Fact]
    public async Task A_list_sits_together_in_one_chunk()
    {
        var chunker = Words(100);
        var list = "- one\n- two\n- three";
        var chunks = await chunker.ChunkAsync("h", list, TestContext.Current.CancellationToken);
        var chunk = Assert.Single(chunks);
        Assert.Equal("h\n" + list, chunk);
    }

    [Fact]
    public async Task A_header_over_the_budget_throws()
    {
        var chunker = Words(2);
        await Assert.ThrowsAsync<InvalidOperationException>(
            () => chunker.ChunkAsync("one two three", "body", TestContext.Current.CancellationToken));
    }
}
