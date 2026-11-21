using Microsoft.EntityFrameworkCore;

namespace Librarian.Adapters.Postgres;

public sealed class LibrarianDbContext(DbContextOptions<LibrarianDbContext> options) : DbContext(options);
