using Librarian.Application.Handlers.Ingest.Extract;
using Librarian.Application.Ports.Ingest;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace Librarian.Adapters.Mistral;

public sealed class ExtractRunOptionsFactory : IExtractRunOptionsFactory
{
    public AgentRunOptions Create(string text)
    {
        var verify = AIFunctionFactory.Create(
            (ExtractDraft draft) => FieldVerifier.Check(draft, text),
            new AIFunctionFactoryOptions
            {
                Name = "verify",
                Description = "Checks the whole draft against the document's text: per field, whether as_written is found in the text "
                    + "and whether value is well formed (a real date, a number). Call it on your draft before you answer; "
                    + "fix what it reports and call it again, then answer with the corrected whole object.",
                SerializerOptions = ExtractJson.Options,
            });

        return new ChatClientAgentRunOptions
        {
            ChatOptions = new ChatOptions { Tools = [verify] },
        };
    }
}
