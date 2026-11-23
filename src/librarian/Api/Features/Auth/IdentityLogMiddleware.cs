namespace Api.Features.Auth;

internal sealed class IdentityLogMiddleware(RequestDelegate next, ILogger<IdentityLogMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context)
    {
        var identity = context.User.Identity;
        if (identity is { IsAuthenticated: true })
        {
            logger.LogInformation(
                "Authenticated request: scheme {Scheme}, name {Name}, email {Email}, subject {Subject}",
                identity.AuthenticationType,
                context.User.Name(),
                context.User.Email(),
                context.User.FindFirst("sub")?.Value);
        }

        await next(context);
    }
}
