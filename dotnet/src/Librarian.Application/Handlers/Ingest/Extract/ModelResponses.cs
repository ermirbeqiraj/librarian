namespace Librarian.Application.Handlers.Ingest.Extract;

public enum FieldKind
{
    Date,
    Number,
    Text,
}

public sealed record FieldDraft(string Name, string Value, string AsWritten, FieldKind Kind);

public sealed record ValidityDraft(string Start, string End, string AsWritten);

public sealed record ExtractDraft(string Kind, ValidityDraft Validity, string Description, List<FieldDraft> Fields);
