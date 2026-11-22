namespace Librarian.Application.Ports.Retrieve;

public interface IKeywordSearch
{
    Task<IReadOnlyList<ChunkHit>> SearchAsync(string query, SearchFilters? filters = null, int limit = 50, CancellationToken cancellationToken = default);
}
