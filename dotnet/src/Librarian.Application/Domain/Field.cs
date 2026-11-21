namespace Librarian.Application.Domain;

public sealed class Field
{
    private Field()
    {
    }

    private Field(string name, string value, string asWritten, bool verified)
    {
        Name = name;
        Value = value;
        AsWritten = asWritten;
        Verified = verified;
    }

    public long Id { get; private set; }
    public long DocumentId { get; private set; }
    public string Name { get; private set; } = null!;
    public string Value { get; private set; } = null!;
    public string AsWritten { get; private set; } = null!;
    public bool Verified { get; private set; }

    internal static Field Create(string name, string value, string asWritten, bool verified)
        => new(name, value, asWritten, verified);
}
