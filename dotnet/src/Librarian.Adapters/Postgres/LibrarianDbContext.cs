using Microsoft.EntityFrameworkCore;

namespace Librarian.Adapters.Postgres;

/// <summary>
/// The library's database context. No tables yet: the first migration comes with the first table.
/// Migrations never run on an app's start; they run as their own step (a migrations bundle, under
/// the owner login).
/// </summary>
public sealed class LibrarianDbContext(DbContextOptions<LibrarianDbContext> options) : DbContext(options);
