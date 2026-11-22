namespace Evals.Refine;

using Application.Ports.Retrieve;

internal static class Text
{
    public static string Period(Period? period)
    {
        if (period is null)
            return "no period";
        return $"{Day(period.From)}..{Day(period.To)}";
    }

    private static string Day(DateOnly? day) => day?.ToString("yyyy-MM-dd") ?? "None";
}
