using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Librarian.Application.Handlers.Ask;
using Npgsql;
using NpgsqlTypes;
using OpenTelemetry;

namespace Librarian.Adapters.Postgres;

public sealed class AskSpanProcessor(string connectionString) : BaseProcessor<Activity>
{
    public override void OnEnd(Activity activity)
    {
        var askId = activity.Baggage.FirstOrDefault(pair => pair.Key == AskTrace.AskId).Value;
        if (askId is null)
            return;
        try
        {
            using var connection = new NpgsqlConnection(connectionString);
            connection.Open();
            using var command = new NpgsqlCommand("INSERT INTO ask_spans (ask_id, at, span) VALUES (@ask_id, @at, @span)", connection);
            command.Parameters.AddWithValue("ask_id", askId);
            command.Parameters.AddWithValue("at", DateTime.UtcNow);
            command.Parameters.AddWithValue("span", NpgsqlDbType.Jsonb, Serialize(activity));
            command.ExecuteNonQuery();
        }
        catch
        {
            // The trace must never break the ask: a span that fails to write is lost.
        }
    }

    private static string Serialize(Activity activity)
    {
        using var stream = new MemoryStream();
        using var writer = new Utf8JsonWriter(stream);
        writer.WriteStartObject();
        writer.WriteString("name", activity.OperationName);
        writer.WriteString("kind", activity.Kind.ToString());
        writer.WriteString("span_id", activity.SpanId.ToString());
        writer.WriteString("parent_id", activity.ParentSpanId.ToString());
        writer.WriteString("started_at", activity.StartTimeUtc.ToString("O"));
        writer.WriteNumber("ms", (long)activity.Duration.TotalMilliseconds);
        var events = activity.Events.ToList();
        if (events.Count > 0)
        {
            writer.WriteStartArray("events");
            foreach (var anEvent in events)
            {
                writer.WriteStartObject();
                writer.WriteString("name", anEvent.Name);
                writer.WritePropertyName("tags");
                writer.WriteStartObject();
                foreach (var tag in anEvent.Tags.Where(tag => tag.Value is not null))
                    writer.WriteString(tag.Key, tag.Value!.ToString());
                writer.WriteEndObject();
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
        }
        writer.WritePropertyName("tags");
        writer.WriteStartObject();
        foreach (var tag in activity.Tags.Where(tag => tag.Value is not null))
            writer.WriteString(tag.Key, tag.Value!.ToString());
        writer.WriteEndObject();
        writer.WriteEndObject();
        writer.Flush();
        return Encoding.UTF8.GetString(stream.ToArray());
    }
}
