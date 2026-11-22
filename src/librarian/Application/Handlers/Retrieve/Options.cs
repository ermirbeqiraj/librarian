
namespace Application.Handlers.Retrieve;

public sealed class RefineOptions
{
    public string BaseUrl { get; set; } = null!;
    public string Model { get; set; } = null!;
    public int ParseRetries { get; set; }

    public void Validate()
    {
        Validation.Required("Refine:BaseUrl", BaseUrl);
        Validation.Required("Refine:Model", Model);
        Positive("Refine:ParseRetries", ParseRetries);
    }

    private static void Positive(string key, int value)
    {
        if (value <= 0)
            throw new InvalidOperationException($"{key} is not set.");
    }
}
