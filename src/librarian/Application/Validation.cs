namespace Application;

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

    internal static void InstructionFileName(string key, string? fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName)
            || Path.IsPathRooted(fileName)
            || Path.GetDirectoryName(fileName) is not "")
            throw new InvalidOperationException($"{key}:Instructions must be a file name under Librarian:Root/instructions.");
    }
}
