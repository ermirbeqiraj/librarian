namespace Librarian.Application.Handlers.Ingest;

public sealed class LibrarianOptions
{
    public string Root { get; set; } = null!;
    public int ScanIntervalSeconds { get; set; }
    public FoldersOptions Folders { get; set; } = null!;

    public string InboxPath => Path.Combine(Root, Folders.Inbox);
    public string ProcessedPath => Path.Combine(Root, Folders.Processed);
    public string ResultsPath => Path.Combine(Root, Folders.Results);
    public string DocumentsPath => Path.Combine(Root, Folders.Documents);

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(Root) || !Path.IsPathRooted(Root))
            throw new InvalidOperationException("Librarian:Root must be an absolute path (appsettings overlay or env var Librarian__Root).");
        if (ScanIntervalSeconds <= 0)
            throw new InvalidOperationException("Librarian:ScanIntervalSeconds is not set.");
        foreach (var (name, folder) in new[]
        {
            ("Inbox", Folders.Inbox), ("Processed", Folders.Processed),
            ("Results", Folders.Results), ("Documents", Folders.Documents),
        })
        {
            if (string.IsNullOrWhiteSpace(folder) || Path.IsPathRooted(folder) || folder.Contains(".."))
                throw new InvalidOperationException($"Librarian:Folders:{name} must be a relative folder, got '{folder}'.");
        }
    }

    public sealed class FoldersOptions
    {
        public string Inbox { get; set; } = null!;
        public string Processed { get; set; } = null!;
        public string Results { get; set; } = null!;
        public string Documents { get; set; } = null!;
    }
}

public sealed class IngestOptions
{
    public DoclingOptions Docling { get; set; } = null!;
    public OcrOptions Ocr { get; set; } = null!;
    public ExtractOptions Extract { get; set; } = null!;

    public void Validate()
    {
        Required("Ingest:Docling", Docling);
        Required("Ingest:Ocr", Ocr);
        Required("Ingest:Extract", Extract);
        Docling.Validate();
        Ocr.Validate();
        Extract.Validate();
    }

    private static void Required(string key, object? section)
    {
        if (section is null)
            throw new InvalidOperationException($"{key} is not set.");
    }

    internal static void Required(string key, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new InvalidOperationException($"{key} is not set.");
    }

    private static void Positive(string key, int value)
    {
        if (value <= 0)
            throw new InvalidOperationException($"{key} is not set.");
    }

    public sealed class DoclingOptions
    {
        public string Url { get; set; } = null!;
        public int TimeoutSeconds { get; set; }

        public void Validate()
        {
            Required("Ingest:Docling:Url", Url);
            Positive("Ingest:Docling:TimeoutSeconds", TimeoutSeconds);
        }
    }

    public sealed class OcrOptions
    {
        public string Url { get; set; } = null!;
        public string Model { get; set; } = null!;
        public int MaxPages { get; set; }
        public int MinCharsPerPage { get; set; }
        public int CallLimit { get; set; }
        public int HardLimit { get; set; }
        public int TimeoutSeconds { get; set; }

        public void Validate()
        {
            Required("Ingest:Ocr:Url", Url);
            Required("Ingest:Ocr:Model", Model);
            Positive("Ingest:Ocr:MaxPages", MaxPages);
            Positive("Ingest:Ocr:MinCharsPerPage", MinCharsPerPage);
            Positive("Ingest:Ocr:CallLimit", CallLimit);
            Positive("Ingest:Ocr:HardLimit", HardLimit);
            Positive("Ingest:Ocr:TimeoutSeconds", TimeoutSeconds);
        }
    }

    public sealed class ExtractOptions
    {
        public string BaseUrl { get; set; } = null!;
        public string Model { get; set; } = null!;
        public string ReasoningEffort { get; set; } = null!;
        public int MaxRounds { get; set; }
        public int HeadPages { get; set; }
        public int TailPages { get; set; }

        public void Validate()
        {
            Required("Ingest:Extract:BaseUrl", BaseUrl);
            Required("Ingest:Extract:Model", Model);
            Required("Ingest:Extract:ReasoningEffort", ReasoningEffort);
            Positive("Ingest:Extract:MaxRounds", MaxRounds);
            Positive("Ingest:Extract:HeadPages", HeadPages);
            Positive("Ingest:Extract:TailPages", TailPages);
        }
    }
}

public sealed class MistralOptions
{
    public string ApiKey { get; set; } = null!;

    public void Validate()
    {
        IngestOptions.Required("Mistral:ApiKey", ApiKey);
    }
}
