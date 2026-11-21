namespace Librarian.Api.Features.Health;

/// <summary>GET /health response: "healthy" when Postgres answers through the DbContext.</summary>
public sealed record HealthResponse(string Status);
