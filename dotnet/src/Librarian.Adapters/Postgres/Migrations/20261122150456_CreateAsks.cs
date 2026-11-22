using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace Librarian.Adapters.Postgres.Migrations
{
    /// <inheritdoc />
    public partial class CreateAsks : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "asks",
                columns: table => new
                {
                    id = table.Column<string>(type: "text", nullable: false),
                    question = table.Column<string>(type: "text", nullable: false),
                    refined_queries = table.Column<string>(type: "jsonb", nullable: false),
                    status = table.Column<string>(type: "text", nullable: true),
                    result = table.Column<string>(type: "jsonb", nullable: true),
                    error = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    completed_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_asks", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "ask_spans",
                columns: table => new
                {
                    id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    ask_id = table.Column<string>(type: "text", nullable: false),
                    at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    span = table.Column<string>(type: "jsonb", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ask_spans", x => x.id);
                    table.ForeignKey(
                        name: "FK_ask_spans_asks_ask_id",
                        column: x => x.ask_id,
                        principalTable: "asks",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_ask_spans_ask_id",
                table: "ask_spans",
                column: "ask_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ask_spans");

            migrationBuilder.DropTable(
                name: "asks");
        }
    }
}
