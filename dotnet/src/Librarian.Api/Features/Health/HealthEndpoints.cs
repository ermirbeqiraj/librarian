using Librarian.Adapters.Postgres;
using Microsoft.EntityFrameworkCore;

namespace Librarian.Api.Features.Health;

/// <summary>GET /health: checks Postgres through the DbContext. No request body, so no Request.cs.</summary>
public static class HealthEndpoints
{
    public static IEndpointRouteBuilder MapHealthEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/health", CheckAsync);
        return app;
    }

    private static async Task<IResult> CheckAsync(LibrarianDbContext db, CancellationToken cancellationToken)
    {
        var healthy = false;
        try
        {
            healthy = await db.Database.CanConnectAsync(cancellationToken);
        }
        catch (Exception)
        {
            // Postgres down or unreachable: unhealthy.
        }

        return healthy
            ? Results.Ok(new HealthResponse("healthy"))
            : Results.Json(new HealthResponse("unhealthy"), statusCode: StatusCodes.Status503ServiceUnavailable);
    }
}
