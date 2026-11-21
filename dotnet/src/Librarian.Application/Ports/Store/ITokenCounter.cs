namespace Librarian.Application.Ports.Store;

public interface ITokenCounter
{
    Task<int> CountAsync(string text, CancellationToken cancellationToken);
}
