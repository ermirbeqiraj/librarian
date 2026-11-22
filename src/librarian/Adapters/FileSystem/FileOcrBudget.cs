using System.Text.Json;
using Application.Handlers.Ingest;
using Application.Ports.Ingest;

namespace Adapters.FileSystem;

public sealed class FileOcrBudget(LibrarianOptions paths, IngestOptions ingest) : IOcrBudget
{
    private readonly object _gate = new();
    private string CounterFile => Path.Combine(paths.Root, "ocr-calls.json");

    public bool TrySpend(out string refusal)
    {
        lock (_gate)
        {
            var (calls, total) = Load();
            if (total >= ingest.Ocr.HardLimit)
            {
                refusal = $"the hard limit of {ingest.Ocr.HardLimit} paid OCR calls is reached, it never resets";
                return false;
            }
            if (calls >= ingest.Ocr.CallLimit)
            {
                refusal = $"the call limit of {ingest.Ocr.CallLimit} is reached; fix the code, then reset the counter file";
                return false;
            }
            Save(calls + 1, total + 1);
            refusal = "";
            return true;
        }
    }

    private (int Calls, int Total) Load()
    {
        if (!File.Exists(CounterFile))
            return (0, 0);
        var state = JsonSerializer.Deserialize<CounterState>(File.ReadAllText(CounterFile));
        return (state?.Calls ?? 0, state?.Total ?? 0);
    }

    private void Save(int calls, int total)
        => File.WriteAllText(CounterFile, JsonSerializer.Serialize(new CounterState(calls, total)));

    private sealed record CounterState(int Calls, int Total);
}
