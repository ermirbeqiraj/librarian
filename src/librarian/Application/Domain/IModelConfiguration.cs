using Microsoft.EntityFrameworkCore;

namespace Application.Domain;

public interface IModelConfiguration
{
    void Configure(ModelBuilder modelBuilder);
}
