using Application.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Adapters.Postgres;

public sealed class AskConfiguration : IEntityTypeConfiguration<Ask>
{
    public void Configure(EntityTypeBuilder<Ask> builder)
    {
        builder.ToTable("asks");
        builder.HasKey(a => a.Id);
        builder.Property(a => a.Id).HasColumnName("id");
        builder.Property(a => a.Question).HasColumnName("question");
        builder.Property(a => a.RefinedJson).HasColumnName("refined_queries").HasColumnType("jsonb");
        builder.Property(a => a.Status).HasColumnName("status");
        builder.Property(a => a.ResultJson).HasColumnName("result").HasColumnType("jsonb");
        builder.Property(a => a.Error).HasColumnName("error");
        builder.Property(a => a.CreatedAt).HasColumnName("created_at");
        builder.Property(a => a.CompletedAt).HasColumnName("completed_at");
        builder.HasMany(a => a.Spans).WithOne().HasForeignKey(s => s.AskId).OnDelete(DeleteBehavior.Cascade);
    }
}

public sealed class AskSpanConfiguration : IEntityTypeConfiguration<AskSpan>
{
    public void Configure(EntityTypeBuilder<AskSpan> builder)
    {
        builder.ToTable("ask_spans");
        builder.HasKey(s => s.Id);
        builder.Property(s => s.Id).HasColumnName("id").ValueGeneratedOnAdd();
        builder.Property(s => s.AskId).HasColumnName("ask_id");
        builder.Property(s => s.At).HasColumnName("at");
        builder.Property(s => s.Span).HasColumnName("span").HasColumnType("jsonb");
    }
}
