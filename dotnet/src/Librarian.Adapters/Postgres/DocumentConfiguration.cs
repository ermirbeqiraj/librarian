using Librarian.Application.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Librarian.Adapters.Postgres;

public sealed class DocumentConfiguration : IEntityTypeConfiguration<Document>
{
    public void Configure(EntityTypeBuilder<Document> builder)
    {
        builder.ToTable("documents");
        builder.HasKey(d => d.Id);
        builder.Property(d => d.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(d => d.Kind).HasColumnName("kind");
        builder.Property(d => d.ValidityStart).HasColumnName("validity_start");
        builder.Property(d => d.ValidityEnd).HasColumnName("validity_end");
        builder.Property(d => d.ValidityAsWritten).HasColumnName("validity_as_written");
        builder.Property(d => d.Description).HasColumnName("description");
        builder.HasMany(d => d.Fields).WithOne().HasForeignKey(f => f.DocumentId);
        builder.HasMany(d => d.Sections).WithOne().HasForeignKey(s => s.DocumentId);
    }
}

public sealed class FieldConfiguration : IEntityTypeConfiguration<Field>
{
    public void Configure(EntityTypeBuilder<Field> builder)
    {
        builder.ToTable("fields");
        builder.HasKey(f => f.Id);
        builder.Property(f => f.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(f => f.DocumentId).HasColumnName("document_id");
        builder.Property(f => f.Name).HasColumnName("name");
        builder.Property(f => f.Value).HasColumnName("value");
        builder.Property(f => f.AsWritten).HasColumnName("as_written");
        builder.Property(f => f.Verified).HasColumnName("verified");
    }
}

public sealed class SectionConfiguration : IEntityTypeConfiguration<Section>
{
    public void Configure(EntityTypeBuilder<Section> builder)
    {
        builder.ToTable("sections");
        builder.HasKey(s => s.Id);
        builder.Property(s => s.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(s => s.DocumentId).HasColumnName("document_id");
        builder.Property(s => s.Position).HasColumnName("position");
        builder.Property(s => s.Heading).HasColumnName("heading");
        builder.Property(s => s.Text).HasColumnName("text");
        builder.HasMany(s => s.Chunks).WithOne().HasForeignKey(c => c.SectionId);
    }
}
