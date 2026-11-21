using Microsoft.EntityFrameworkCore;

namespace Librarian.Application.Domain;

public interface IModelConfiguration
{
    void Configure(ModelBuilder modelBuilder);
}
