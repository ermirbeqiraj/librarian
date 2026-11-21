namespace Librarian.Application.Ports.Ingest;

public interface IOcrBudget
{
    bool TrySpend(out string refusal);
}
