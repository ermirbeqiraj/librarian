using System.Text.Json;
using System.Text.Json.Serialization;

namespace Application.Handlers.Ingest.Extract;

public static class ExtractJson
{
    public static readonly JsonSerializerOptions Options = ExtractJsonContext.Default.Options;
}

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web, Converters = [typeof(JsonStringEnumConverter<FieldKind>)])]
[JsonSerializable(typeof(FieldKind))]
[JsonSerializable(typeof(FieldDraft))]
[JsonSerializable(typeof(ValidityDraft))]
[JsonSerializable(typeof(ExtractDraft))]
[JsonSerializable(typeof(FieldCheck))]
[JsonSerializable(typeof(VerifyReport))]
[JsonSerializable(typeof(Validity))]
[JsonSerializable(typeof(ExtractedField))]
[JsonSerializable(typeof(Extracted))]
[JsonSerializable(typeof(FieldCatalog.KindEntry))]
[JsonSerializable(typeof(FieldCatalog.CatalogFile))]
public partial class ExtractJsonContext : JsonSerializerContext;

public sealed record Validity(string? Start, string? End, string? AsWritten);

public sealed record ExtractedField(string Name, string Value, string AsWritten, bool Verified);

public sealed record Extracted(string Kind, Validity Validity, string Description, List<ExtractedField> Fields);
