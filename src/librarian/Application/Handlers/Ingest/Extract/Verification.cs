namespace Application.Handlers.Ingest.Extract;

public sealed record FieldCheck(string Name, bool Found, bool WellFormed, string Message);

public sealed record VerifyReport(List<FieldCheck> Checks, string Summary);
