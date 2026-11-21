namespace Librarian.Application.Handlers.Store;

public sealed class StoreOptions
{
    public int ScanIntervalSeconds { get; set; }
    public int MaxTries { get; set; }
    public EmbeddingOptions Embedding { get; set; } = null!;

    public void Validate()
    {
        Positive("Store:ScanIntervalSeconds", ScanIntervalSeconds);
        Positive("Store:MaxTries", MaxTries);
        if (Embedding is null)
            throw new InvalidOperationException("Store:Embedding is not set.");
        Embedding.Validate();
    }

    private static void Positive(string key, int value)
    {
        if (value <= 0)
            throw new InvalidOperationException($"{key} is not set.");
    }

    private static void Required(string key, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new InvalidOperationException($"{key} is not set.");
    }

    public sealed class EmbeddingOptions
    {
        public string Url { get; set; } = null!;
        public string Model { get; set; } = null!;
        public int Dimensions { get; set; }
        public int TokenBudget { get; set; }
        public int BatchSize { get; set; }
        public int TimeoutSeconds { get; set; }

        public void Validate()
        {
            Required("Store:Embedding:Url", Url);
            Required("Store:Embedding:Model", Model);
            Positive("Store:Embedding:Dimensions", Dimensions);
            Positive("Store:Embedding:TokenBudget", TokenBudget);
            Positive("Store:Embedding:BatchSize", BatchSize);
            Positive("Store:Embedding:TimeoutSeconds", TimeoutSeconds);
        }
    }
}
