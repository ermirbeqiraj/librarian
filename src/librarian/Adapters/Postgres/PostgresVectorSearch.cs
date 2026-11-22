using System.Globalization;
using System.Text;
using Application.Domain;
using Application.Ports.Retrieve;
using Microsoft.Extensions.AI;
using Npgsql;
using NpgsqlTypes;

namespace Adapters.Postgres;

public sealed class PostgresVectorSearch(
    LibrarianDbContext db,
    IEmbeddingGenerator<string, Embedding<float>> embedder) : IVectorSearch
{
    public async Task<IReadOnlyList<ChunkHit>> SearchAsync(
        string query, SearchFilters? filters = null, int limit = 50, CancellationToken cancellationToken = default)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(limit, 1);
        var generated = await embedder.GenerateAsync([query], cancellationToken: cancellationToken);
        List<Embedding<float>> vectors = [.. generated];
        if (vectors.Count != 1)
            throw new InvalidOperationException($"TEI returned {vectors.Count} vectors for 1 query.");
        var literal = "[" + string.Join(",", vectors[0].Vector.ToArray().Select(v => v.ToString("R", CultureInfo.InvariantCulture))) + "]";

        var sql = new StringBuilder("""
            WITH q AS (SELECT CAST(@vector AS vector) AS vector)
            SELECT c.id, c.section_id
            FROM chunks c
            JOIN sections s ON s.id = c.section_id
            JOIN documents d ON d.id = s.document_id
            CROSS JOIN q
            WHERE TRUE
            """);
        var parameters = new List<NpgsqlParameter> { new("vector", NpgsqlDbType.Text) { Value = literal } };
        var (filterSql, filterParameters) = SearchSql.Filters(filters);
        sql.Append(filterSql);
        parameters.AddRange(filterParameters);
        sql.Append("""

            ORDER BY c.embedding <=> q.vector, c.id
            LIMIT @limit
            """);
        parameters.Add(new NpgsqlParameter("limit", NpgsqlDbType.Integer) { Value = limit });

        return await SearchSql.ReadHitsAsync(db, sql.ToString(), parameters, cancellationToken);
    }
}
