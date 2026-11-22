using System.Text;
using Librarian.Application.Domain;
using Librarian.Application.Ports.Retrieve;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using NpgsqlTypes;

namespace Librarian.Adapters.Postgres;

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
        if (filters.Period is not null)
        {
            sql.Append(" AND (d.validity_start IS NULL OR ").Append(Predicate(filters.Period.Op)).Append(')');
            parameters.Add(new NpgsqlParameter("period_start", NpgsqlDbType.Date) { Value = filters.Period.Start });
            parameters.Add(new NpgsqlParameter("period_end", NpgsqlDbType.Date) { Value = filters.Period.DayAfter });
        }
        return (sql.ToString(), parameters);
    }

    private static string Predicate(PeriodOp op) => op switch
    {
        PeriodOp.During => "d.validity_start::date < @period_end AND (d.validity_end IS NULL OR d.validity_end::date >= @period_start)",
        PeriodOp.After => "d.validity_end IS NULL OR d.validity_end::date >= @period_end",
        PeriodOp.Before => "d.validity_start::date < @period_start",
        PeriodOp.On => "d.validity_start::date <= @period_start AND (d.validity_end IS NULL OR d.validity_end::date >= @period_start)",
        _ => throw new ArgumentOutOfRangeException(nameof(op), op, "unknown period op."),
    };
}
