using Application.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Adapters.Postgres;

public sealed class IngestionConfiguration : IEntityTypeConfiguration<Ingestion>
{
    public void Configure(EntityTypeBuilder<Ingestion> builder)
    {
        builder.ToTable("ingestions");
        builder.HasKey(i => i.Id);
        builder.Property(i => i.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(i => i.FileName).HasColumnName("file_name");
        builder.Property(i => i.FileSize).HasColumnName("file_size");
        builder.Property(i => i.State).HasColumnName("state").HasConversion<string>();
        builder.Property(i => i.ReadBy).HasColumnName("read_by").HasConversion<string>();
        builder.Property(i => i.ReadText).HasColumnName("read_text");
        builder.Property(i => i.TextHash).HasColumnName("text_hash");
        builder.Property(i => i.ExtractedJson).HasColumnName("extracted_json").HasColumnType("jsonb");
        builder.Property(i => i.Tries).HasColumnName("tries");
        builder.Property(i => i.ErrorReason).HasColumnName("error_reason").HasConversion<string>();
        builder.Property(i => i.ErrorMessage).HasColumnName("error_message");
        builder.Property(i => i.CreatedAt).HasColumnName("created_at");
        builder.Property(i => i.UpdatedAt).HasColumnName("updated_at");
        builder.Property(i => i.DocumentId).HasColumnName("document_id");
        builder.HasIndex(i => i.TextHash);
        builder.HasOne(i => i.Document).WithOne().HasForeignKey<Ingestion>(i => i.DocumentId);
    }
}
