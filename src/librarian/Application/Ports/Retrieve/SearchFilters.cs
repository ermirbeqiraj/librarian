namespace Application.Ports.Retrieve;

public sealed record SearchFilters(Period? Period = null, string? Kind = null, IReadOnlyList<long>? DocumentIds = null);
