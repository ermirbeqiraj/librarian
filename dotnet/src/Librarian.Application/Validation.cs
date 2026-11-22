namespace Librarian.Application;

internal static class Validation
{
    internal static void Required(string key, object? section)
    {
        if (section is null)
            throw new InvalidOperationException($"{key} is not set.");
    }

    internal static void Required(string key, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new InvalidOperationException($"{key} is not set.");
    }
}
