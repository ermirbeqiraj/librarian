using System.Text.Json;

namespace Librarian.Evals.Common;

internal static class Json
{
    public static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };
}
