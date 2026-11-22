namespace Evals;

public sealed class EvalsOptions
{
    public string Root { get; set; } = null!;

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(Root))
            throw new InvalidOperationException("Evals:Root is not set.");
    }
}
