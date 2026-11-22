namespace Application.Ports.Retrieve;

public interface IVectorSearch
{
    Task<IReadOnlyList<ChunkHit>> SearchAsync(string query, SearchFilters? filters = null, int limit = 50, CancellationToken cancellationToken = default);
}
