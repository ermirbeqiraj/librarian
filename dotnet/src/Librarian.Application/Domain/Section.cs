namespace Librarian.Application.Domain;

public sealed class Section
{
    private Section()
    {
    }

    private Section(int position, string heading, string text)
    {
        Position = position;
        Heading = heading;
        Text = text;
    }

    public long Id { get; private set; }
    public long DocumentId { get; private set; }
    public int Position { get; private set; }
    public string Heading { get; private set; } = null!;
    public string Text { get; private set; } = null!;
    public List<Chunk> Chunks { get; } = [];

    internal static Section Create(int position, string heading, string text) => new(position, heading, text);

    public void AddChunk(string text, float[] embedding) => Chunks.Add(Chunk.Create(Chunks.Count, text, embedding));
}
