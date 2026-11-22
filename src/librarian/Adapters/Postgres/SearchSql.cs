using System.Text;
using Application.Domain;
using Application.Ports.Retrieve;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using NpgsqlTypes;

namespace Adapters.Postgres;

internal static class SearchSql
{
    public static async Task<IReadOnlyList<ChunkHit>> ReadHitsAsync(
        LibrarianDbContext db, string sql, List<NpgsqlParameter> parameters, CancellationToken cancellationToken)
    {
        await db.Database.OpenConnectionAsync(cancellationToken);
        var connection = (NpgsqlConnection)db.Database.GetDbConnection();
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        foreach (var parameter in parameters)
            command.Parameters.Add(parameter);
        var hits = new List<ChunkHit>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
            hits.Add(new ChunkHit(reader.GetInt64(0), reader.GetInt64(1), hits.Count + 1L));
        return hits;
    }

    public static (string Sql, List<NpgsqlParameter> Parameters) Filters(SearchFilters? filters)
    {
        if (filters is null)
            return ("", []);
        var sql = new StringBuilder();
        var parameters = new List<NpgsqlParameter>();
        if (filters.Kind is not null)
        {
            sql.Append(" AND d.kind = @kind");
            parameters.Add(new NpgsqlParameter("kind", NpgsqlDbType.Text) { Value = filters.Kind });
        }
        if (filters.DocumentIds is not null)
        {
            sql.Append(" AND s.document_id = ANY(@document_ids)");
            parameters.Add(new NpgsqlParameter("document_ids", NpgsqlDbType.Array | NpgsqlDbType.Bigint) { Value = filters.DocumentIds.ToArray() });
        }
        if (filters.Period is { } period)
        {
            var overlap = new List<string>();
            if (period.To is { } to)
            {
                overlap.Add("d.validity_start::date <= @period_to");
                parameters.Add(new NpgsqlParameter("period_to", NpgsqlDbType.Date) { Value = to });
            }
            if (period.From is { } from)
            {
                overlap.Add("(d.validity_end IS NULL OR d.validity_end::date >= @period_from)");
                parameters.Add(new NpgsqlParameter("period_from", NpgsqlDbType.Date) { Value = from });
            }
            if (overlap.Count > 0)
                sql.Append(" AND (d.validity_start IS NULL OR (").Append(string.Join(" AND ", overlap)).Append("))");
        }
        return (sql.ToString(), parameters);
    }
}
