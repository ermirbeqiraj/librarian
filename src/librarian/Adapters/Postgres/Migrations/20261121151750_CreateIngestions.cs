using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace Adapters.Postgres.Migrations
{
    /// <inheritdoc />
    public partial class CreateIngestions : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "ingestions",
                columns: table => new
                {
                    id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    file_name = table.Column<string>(type: "text", nullable: false),
                    file_size = table.Column<long>(type: "bigint", nullable: false),
                    state = table.Column<string>(type: "text", nullable: false),
                    read_by = table.Column<string>(type: "text", nullable: true),
                    read_text = table.Column<string>(type: "text", nullable: true),
                    text_hash = table.Column<string>(type: "text", nullable: true),
                    extracted_json = table.Column<string>(type: "jsonb", nullable: true),
                    tries = table.Column<int>(type: "integer", nullable: false),
                    error_reason = table.Column<string>(type: "text", nullable: true),
                    error_message = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updated_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    document_id = table.Column<long>(type: "bigint", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ingestions", x => x.id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_ingestions_text_hash",
                table: "ingestions",
                column: "text_hash");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ingestions");
        }
    }
}
