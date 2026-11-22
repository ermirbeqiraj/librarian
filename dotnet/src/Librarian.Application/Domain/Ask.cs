namespace Librarian.Application.Domain;

public sealed class Ask
{
    private Ask()
    {
    }

    private Ask(string id, string question, string refinedJson, DateTime createdAt)
    {
        Id = id;
        Question = question;
        RefinedJson = refinedJson;
        CreatedAt = createdAt;
    }

    public string Id { get; private set; } = null!;
    public string Question { get; private set; } = null!;
    public string RefinedJson { get; private set; } = null!;
    public string? Status { get; private set; }
    public string? ResultJson { get; private set; }
    public string? Error { get; private set; }
    public DateTime CreatedAt { get; private set; }
    public DateTime? CompletedAt { get; private set; }
    public List<AskSpan> Spans { get; } = [];

    public static Ask Create(string id, string question, string refinedJson, DateTime createdAt)
        => new(id, question, refinedJson, createdAt);

    public void MarkCompleted(string status, string resultJson, DateTime at)
    {
        Status = status;
        ResultJson = resultJson;
        CompletedAt = at;
    }

    public void MarkFailed(string error, DateTime at)
    {
        Status = "error";
        Error = error;
        CompletedAt = at;
    }
}

public sealed class AskSpan
{
    private AskSpan()
    {
    }

    private AskSpan(string askId, DateTime at, string span)
    {
        AskId = askId;
        At = at;
        Span = span;
    }

    public long Id { get; private set; }
    public string AskId { get; private set; } = null!;
    public DateTime At { get; private set; }
    public string Span { get; private set; } = null!;

    public static AskSpan Create(string askId, DateTime at, string span)
        => new(askId, at, span);
}
