using Application.Domain;

namespace Api.Features.Health;

public static class HealthEndpoints
{
    public static IEndpointRouteBuilder MapHealthEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/health", CheckAsync).AllowAnonymous();
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

        }

        return healthy
            ? Results.Ok(new HealthResponse("healthy"))
            : Results.Json(new HealthResponse("unhealthy"), statusCode: StatusCodes.Status503ServiceUnavailable);
    }
}
