using Application.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using NpgsqlTypes;
using Pgvector;

namespace Adapters.Postgres;

public sealed class ChunkConfiguration : IEntityTypeConfiguration<Chunk>
{
    public void Configure(EntityTypeBuilder<Chunk> builder)
    {
        builder.ToTable("chunks");
        builder.HasKey(c => c.Id);
        builder.Property(c => c.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(c => c.SectionId).HasColumnName("section_id");
        builder.Property(c => c.Position).HasColumnName("position");
        builder.Property(c => c.Text).HasColumnName("text");
        builder.Property(c => c.Embedding)
            .HasColumnName("embedding")
            .HasConversion(vector => new Vector(vector), vector => vector.ToArray())
            .HasColumnType("vector(1024)");
        builder.Property<NpgsqlTsVector>("SearchText")
            .HasColumnName("search_text")
            .HasComputedColumnSql("to_tsvector('italian', unaccent_immutable(text))", stored: true)
            .IsRequired();
        builder.HasIndex("SearchText").HasMethod("gin");
    }
}
