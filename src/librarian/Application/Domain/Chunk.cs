namespace Application.Domain;

public sealed class Chunk
{
    private Chunk()
    {
    }

    private Chunk(int position, string text, float[] embedding)
    {
        Position = position;
        Text = text;
        Embedding = embedding;
    }

    public long Id { get; private set; }
    public long SectionId { get; private set; }
    public int Position { get; private set; }
    public string Text { get; private set; } = null!;
    public float[] Embedding { get; private set; } = null!;

    internal static Chunk Create(int position, string text, float[] embedding) => new(position, text, embedding);
}
