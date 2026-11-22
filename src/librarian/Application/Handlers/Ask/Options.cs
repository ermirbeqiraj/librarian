namespace Application.Handlers.Ask;

public sealed class AskOptions
{
    public string BaseUrl { get; set; } = null!;
    public string Model { get; set; } = null!;
    public string ReasoningEffort { get; set; } = null!;
    public int MaxRounds { get; set; }
    public string InstructionsPath { get; set; } = null!;
    public string? FileUrl { get; set; }
    public int TimeoutSeconds { get; set; } = 480;

    public void Validate()
    {
        Validation.Required("Ask:BaseUrl", BaseUrl);
        Validation.Required("Ask:Model", Model);
        if (ReasoningEffort is not ("low" or "medium" or "high"))
            throw new InvalidOperationException($"Ask:ReasoningEffort '{ReasoningEffort}' is not one of low, medium, high.");
        if (MaxRounds < 1)
            throw new InvalidOperationException("Ask:MaxRounds is not set.");
        if (string.IsNullOrWhiteSpace(InstructionsPath) || !Path.IsPathRooted(InstructionsPath))
            throw new InvalidOperationException("Ask:InstructionsPath must be an absolute path (appsettings overlay or env var).");
        if (TimeoutSeconds < 1)
            throw new InvalidOperationException("Ask:TimeoutSeconds must be at least 1 second.");
        if (FileUrl is not null && !FileUrl.Contains("{path}"))
            throw new InvalidOperationException("Ask:FileUrl must hold '{path}' where the file's path goes, or stay unset.");
    }
}

public sealed class AskRetentionOptions
{
    public int Days { get; set; }
    public int ScanMinutes { get; set; }

    public void Validate()
    {
        if (Days < 1)
            throw new InvalidOperationException("Ask:Retention:Days is not set.");
        if (ScanMinutes < 1)
            throw new InvalidOperationException("Ask:Retention:ScanMinutes is not set.");
    }
}
