namespace Application.Handlers.Serve;

public sealed record SectionPull(
    long SectionId,
    long DocumentId,
    string Kind,
    string? Heading,
    int Position,
    int Of,
    string Text,
    string? File);

public sealed record DocumentCard(
    long DocumentId,
    string Kind,
    string Description,
    CardValidity? Validity,
    int DocumentChars,
    List<CardSection> Sections,
    string? File);

public sealed record CardValidity(string? From, string? To, string? AsWritten);

public sealed record CardSection(long SectionId, int Position, string? Heading);

public sealed record LibraryShelf(int Documents, List<ShelfGroup> Groups);

public sealed record ShelfGroup(string Kind, string? Issuer, int Documents, ShelfPeriod? Validity);

public sealed record ShelfPeriod(string? From, string? To);
