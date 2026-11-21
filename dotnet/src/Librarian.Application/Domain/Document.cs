using Librarian.Application.Handlers.Ingest.Extract;

namespace Librarian.Application.Domain;

public sealed class Document
{
    private Document()
    {
    }

    private Document(Extracted extracted)
    {
        Kind = extracted.Kind;
        ValidityStart = extracted.Validity.Start;
        ValidityEnd = extracted.Validity.End;
        ValidityAsWritten = extracted.Validity.AsWritten;
        Description = extracted.Description;
        foreach (var field in extracted.Fields)
            Fields.Add(Field.Create(field.Name, field.Value, field.AsWritten, field.Verified));
    }

    public long Id { get; private set; }
    public string Kind { get; private set; } = null!;
    public string? ValidityStart { get; private set; }
    public string? ValidityEnd { get; private set; }
    public string? ValidityAsWritten { get; private set; }
    public string Description { get; private set; } = null!;
    public List<Field> Fields { get; } = [];
    public List<Section> Sections { get; } = [];

    public static Document Create(Extracted extracted) => new(extracted);

    public Section AddSection(string heading, string text)
    {
        var section = Section.Create(Sections.Count, heading, text);
        Sections.Add(section);
        return section;
    }
}
