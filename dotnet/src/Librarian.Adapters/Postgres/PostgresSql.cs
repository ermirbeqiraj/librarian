using System.Text.Json;
using Librarian.Application.Ports.Ask;
using Npgsql;

namespace Librarian.Adapters.Postgres;

public sealed class PostgresSql(string connectionString) : ISql
{
    public const int MaxRows = 200;
    public const string TooManyRows = "too many rows: aggregate in SQL or add a LIMIT";

    // A bit later than the reader role's own 5 s statement_timeout, so the database's timeout
    // normally fires first and the agent reads that error.
    public const int CancelSeconds = 6;

    private static readonly TimeSpan Cancel = TimeSpan.FromSeconds(CancelSeconds);
    private static readonly string Cancelled = $"stopped after {CancelSeconds} s: make the query cheaper";

    private Schema? schema;

    public async Task<SqlResult> RunAsync(string query, CancellationToken cancellationToken = default)
    {
        using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        await using var connection = new NpgsqlConnection(connectionString);
        await connection.OpenAsync(cancellationToken);
        try
        {
            using var command = connection.CreateCommand();
            command.CommandText = Wrapped(query);
            await command.PrepareAsync(cancellation.Token);
            cancellation.CancelAfter(Cancel);
            using var reader = await command.ExecuteReaderAsync(cancellation.Token);
            return await CollectAsync(reader, cancellation.Token);
        }
        catch (Exception ex)
        {
            if (ex is OperationCanceledException && !cancellationToken.IsCancellationRequested)
                return SqlResult.Failed(Cancelled);
            return SqlResult.Failed(Message(ex));
        }
    }

    public async Task<SqlResult> LibraryAsync(CancellationToken cancellationToken = default)
    {
        const string LibrarySql = """
            SELECT d.kind, f.value AS issuer, count(*) AS documents,
                   min(d.validity_start) AS first, max(d.validity_end) AS last
            FROM documents d
            LEFT JOIN fields f ON f.document_id = d.id AND f.name = 'issuer'
            GROUP BY d.kind, f.value
            ORDER BY d.kind, f.value
            """;
        return await RunAsync(LibrarySql, cancellationToken);
    }

    public async Task<Schema> SchemaAsync(CancellationToken cancellationToken = default)
    {
        if (schema is not null)
            return schema;
        const string TablesSql = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('documents', 'fields', 'sections')
            ORDER BY table_name, ordinal_position
            """;
        const string KeysSql = """
            SELECT f.name AS key,
                   count(*) AS document_count,
                   array_agg(DISTINCT d.kind ORDER BY d.kind) AS kinds,
                   (array_agg(f.value ORDER BY f.document_id DESC))[1] AS example
            FROM fields f
            JOIN documents d ON d.id = f.document_id
            GROUP BY f.name
            ORDER BY document_count DESC, f.name
            LIMIT 100
            """;
        await using var connection = new NpgsqlConnection(connectionString);
        await connection.OpenAsync(cancellationToken);
        var tables = new Dictionary<string, Table>();
        await using (var command = new NpgsqlCommand(TablesSql, connection))
        await using (var reader = await command.ExecuteReaderAsync(cancellationToken))
        {
            while (await reader.ReadAsync(cancellationToken))
            {
                var name = reader.GetString(0);
                if (!tables.TryGetValue(name, out var table))
                    tables[name] = table = new Table(name, []);
                table.Columns.Add(new Column(reader.GetString(1), reader.GetString(2)));
            }
        }
        var keys = new List<FieldKey>();
        await using (var command = new NpgsqlCommand(KeysSql, connection))
        await using (var reader = await command.ExecuteReaderAsync(cancellationToken))
        {
            while (await reader.ReadAsync(cancellationToken))
            {
                keys.Add(new FieldKey(
                    reader.GetString(0),
                    reader.GetInt32(1),
                    [.. (string[])reader.GetValue(2)],
                    Json(reader.GetFieldValue<object>(3))));
            }
        }
        schema = new Schema([.. tables.Values], keys);
        return schema;
    }

    internal static string Wrapped(string query)
    {
        var body = query.Trim();
        while (body.EndsWith(';'))
            body = body[..^1].TrimEnd();
        return $"SELECT * FROM (\n{body}\n) AS q LIMIT {MaxRows + 1}";
    }

    private static async Task<SqlResult> CollectAsync(NpgsqlDataReader reader, CancellationToken cancellationToken)
    {
        var columns = new List<string>();
        for (var index = 0; index < reader.FieldCount; index++)
        {
            var name = reader.GetName(index);
            if (columns.Contains(name))
                return SqlResult.Failed($"two columns are named '{name}': name them apart with AS");
            columns.Add(name);
        }
        var rows = new List<Dictionary<string, JsonElement>>();
        while (rows.Count <= MaxRows && await reader.ReadAsync(cancellationToken))
        {
            var row = new Dictionary<string, JsonElement>();
            for (var index = 0; index < reader.FieldCount; index++)
                row[columns[index]] = Json(reader.GetValue(index));
            rows.Add(row);
        }
        if (rows.Count > MaxRows)
            return SqlResult.Failed(TooManyRows);
        return new SqlResult(columns, rows, null);
    }

    private static JsonElement Json(object value)
    {
        return value switch
        {
            DBNull => JsonDocument.Parse("null").RootElement,
            bool b => JsonDocument.Parse(b ? "true" : "false").RootElement,
            short or int or long or decimal or float or double
                => JsonDocument.Parse(Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture)!).RootElement,
            string s => JsonSerializer.SerializeToElement(s),
            DateTime d => JsonSerializer.SerializeToElement(d.Kind switch
            {
                DateTimeKind.Utc => d.ToString("yyyy-MM-dd'T'HH:mm:ssK"),
                _ => d.ToString("yyyy-MM-dd'T'HH:mm:ss' 'K"),
            }),
            DateOnly day => JsonSerializer.SerializeToElement(day.ToString("yyyy-MM-dd")),
            TimeOnly time => JsonSerializer.SerializeToElement(time.ToString("HH:mm:ss")),
            _ => JsonSerializer.SerializeToElement(value.ToString()),
        };
    }

    private static string Message(Exception error)
        => error is PostgresException pg ? pg.MessageText : error.Message;
}
