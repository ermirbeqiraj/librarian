using Application.Domain;
using Application.Handlers.Ask;
using Application.Handlers.Ingest;
using Microsoft.EntityFrameworkCore;

namespace Application.Handlers.Serve;

public sealed class ServeHandler(LibrarianDbContext db, LibrarianOptions paths, AskOptions options)
{
    public async Task<SectionPull?> PullAsync(long sectionId, CancellationToken cancellationToken = default)
    {
        var section = await db.Set<Section>().AsNoTracking()
            .Where(s => s.Id == sectionId)
            .Select(s => new { s.Id, s.DocumentId, s.Position, s.Heading, s.Text })
            .FirstOrDefaultAsync(cancellationToken);
        if (section is null)
            return null;
        var document = await db.Documents.AsNoTracking()
            .Where(d => d.Id == section.DocumentId)
            .Select(d => d.Kind)
            .FirstOrDefaultAsync(cancellationToken);
        if (document is null)
            return null;
        var of = await db.Set<Section>().AsNoTracking()
            .CountAsync(s => s.DocumentId == section.DocumentId, cancellationToken);
        var file = await FileAsync(section.DocumentId, cancellationToken);
        return new SectionPull(
            section.Id, section.DocumentId, document, section.Heading,
            section.Position + 1, of, section.Text, file);
    }

    public async Task<DocumentCard?> CardAsync(long documentId, CancellationToken cancellationToken = default)
    {
        var document = await db.Documents.AsNoTracking()
            .Where(d => d.Id == documentId)
            .Select(d => new { d.Kind, d.Description, d.ValidityStart, d.ValidityEnd, d.ValidityAsWritten })
            .FirstOrDefaultAsync(cancellationToken);
        if (document is null)
            return null;
        var sections = await db.Set<Section>().AsNoTracking()
            .Where(s => s.DocumentId == documentId)
            .OrderBy(s => s.Position)
            .Select(s => new CardSection(s.Id, s.Position + 1, s.Heading))
            .ToListAsync(cancellationToken);
        var chars = await db.Set<Section>().AsNoTracking()
            .Where(s => s.DocumentId == documentId)
            .SumAsync(s => s.Text.Length, cancellationToken);
        var none = document.ValidityStart is null && document.ValidityEnd is null
            && document.ValidityAsWritten is null;
        CardValidity? validity = none
            ? null
            : new(document.ValidityStart, document.ValidityEnd, document.ValidityAsWritten);
        var file = await FileAsync(documentId, cancellationToken);
        return new DocumentCard(documentId, document.Kind, document.Description, validity, chars, sections, file);
    }

    public async Task<LibraryShelf> ShelfAsync(CancellationToken cancellationToken = default)
    {
        var documents = await db.Documents.AsNoTracking()
            .Select(d => new { d.Id, d.Kind, d.ValidityStart, d.ValidityEnd })
            .ToListAsync(cancellationToken);
        var issuers = await db.Set<Field>().AsNoTracking()
            .Where(f => f.Name == "issuer")
            .Select(f => new { f.DocumentId, f.Value })
            .ToListAsync(cancellationToken);
        var byDocument = issuers.ToDictionary(issuer => issuer.DocumentId, issuer => issuer.Value);
        var groups = documents
            .GroupBy(document => (document.Kind, Issuer: byDocument.GetValueOrDefault(document.Id)))
            .Select(group =>
            {
                var starts = group.Where(d => d.ValidityStart is not null).Select(d => d.ValidityStart).ToList();
                var ends = group.Where(d => d.ValidityEnd is not null).Select(d => d.ValidityEnd).ToList();
                return new ShelfGroup(
                    group.Key.Kind,
                    group.Key.Issuer,
                    group.Count(),
                    starts.Count > 0 || ends.Count > 0
                        ? new ShelfPeriod(starts.Count > 0 ? starts.Min() : null, ends.Count > 0 ? ends.Max() : null)
                        : null);
            })
            .OrderBy(group => group.Kind)
            .ThenByDescending(group => group.Documents)
            .ToList();
        return new LibraryShelf(documents.Count, groups);
    }

    private async Task<string?> FileAsync(long documentId, CancellationToken cancellationToken)
    {
        if (options.FileUrl is null)
            return null;
        var name = await db.Ingestions.AsNoTracking()
            .Where(i => i.DocumentId == documentId)
            .Select(i => i.FileName)
            .FirstOrDefaultAsync(cancellationToken);
        if (name is null)
            return null;
        var path = Uri.EscapeDataString(Path.Combine(paths.ProcessedPath, name));
        return options.FileUrl.Replace("{path}", path);
    }
}
