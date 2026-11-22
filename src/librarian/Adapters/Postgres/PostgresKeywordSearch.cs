using System.Text;
using Application.Domain;
using Application.Ports.Retrieve;
using Npgsql;
using NpgsqlTypes;

namespace Adapters.Postgres;

public sealed class PostgresKeywordSearch(LibrarianDbContext db) : IKeywordSearch
{
    public async Task<IReadOnlyList<ChunkHit>> SearchAsync(
        string query, SearchFilters? filters = null, int limit = 50, CancellationToken cancellationToken = default)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(limit, 1);

        var sql = new StringBuilder("""
            WITH q AS (SELECT websearch_to_tsquery('italian', unaccent_immutable(@query)) AS query)
            SELECT c.id, c.section_id
            FROM chunks c
            JOIN sections s ON s.id = c.section_id
            JOIN documents d ON d.id = s.document_id
            CROSS JOIN q
            WHERE c.search_text @@ q.query
            """);
        var parameters = new List<NpgsqlParameter> { new("query", NpgsqlDbType.Text) { Value = query } };
        var (filterSql, filterParameters) = SearchSql.Filters(filters);
        sql.Append(filterSql);
        parameters.AddRange(filterParameters);
        sql.Append("""

            ORDER BY ts_rank(c.search_text, q.query) DESC, c.id
            LIMIT @limit
            """);
        parameters.Add(new NpgsqlParameter("limit", NpgsqlDbType.Integer) { Value = limit });

        return await SearchSql.ReadHitsAsync(db, sql.ToString(), parameters, cancellationToken);
    }
}
