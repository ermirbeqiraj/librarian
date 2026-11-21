using System.Security.Cryptography;
using System.Text;

namespace Librarian.Application.Domain;

public enum IngestionState
{
    Started,
    Extracted,
    Embedded,
    Error,
}

public enum IngestionErrorReason
{
    ReadFailed,
    ExtractFailed,
    Duplicate,
    EmbedFailed,
    SaveFailed,
}

public enum ReadBy
{
    Docling,
    Ocr,
}

public sealed class Ingestion
{
    private Ingestion()
    {
    }

    private Ingestion(string fileName, long fileSize, DateTime now)
    {
        FileName = fileName;
        FileSize = fileSize;
        State = IngestionState.Started;
        CreatedAt = now;
        UpdatedAt = now;
    }

    public long Id { get; private set; }
    public string FileName { get; private set; } = null!;
    public long FileSize { get; private set; }
    public IngestionState State { get; private set; }
    public ReadBy? ReadBy { get; private set; }
    public string? ReadText { get; private set; }
    public string? TextHash { get; private set; }
    public string? ExtractedJson { get; private set; }
    public int Tries { get; private set; }
    public IngestionErrorReason? ErrorReason { get; private set; }
    public string? ErrorMessage { get; private set; }
    public DateTime CreatedAt { get; private set; }
    public DateTime UpdatedAt { get; private set; }
    public long? DocumentId { get; private set; }
    public Document? Document { get; private set; }

    public static Ingestion Create(string fileName, long fileSize) => new(fileName, fileSize, DateTime.UtcNow);

    public void MarkRead(ReadBy readBy, string text)
    {
        ReadBy = readBy;
        ReadText = text;
        TextHash = ComputeTextHash(text);
        Touch();
    }

    private static string ComputeTextHash(string text)
        => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();

    public void MarkExtracted(string extractedJson)
    {
        ExtractedJson = extractedJson;
        State = IngestionState.Extracted;
        ErrorReason = null;
        ErrorMessage = null;
        Touch();
    }

    public void MarkEmbedded(Document document)
    {
        Document = document;
        State = IngestionState.Embedded;
        ErrorReason = null;
        ErrorMessage = null;
        Touch();
    }

    public void MarkError(IngestionErrorReason reason, string message)
    {
        Document = null;
        DocumentId = null;
        State = IngestionState.Error;
        ErrorReason = reason;
        ErrorMessage = message;
        Touch();
    }

    public void CountTry()
    {
        Tries++;
        Touch();
    }

    private void Touch() => UpdatedAt = DateTime.UtcNow;
}
