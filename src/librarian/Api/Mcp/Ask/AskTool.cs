using System.ComponentModel;
using Application.Handlers.Ask;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

namespace Api.Mcp.Ask;

[McpServerToolType]
internal sealed class AskTool(AskHandler handler)
{
    [McpServerTool(OpenWorld = false)]
    [Description("""
        Ask the library one question about the home's documents — bills, receipts, contracts, letters: an amount,
        a date, a condition, whether something was paid or sent. The question must stand alone, with the names,
        dates and amounts it is about, as the user spoke them; this server keeps no conversation.

        The answer is a verdict with its story — status (found | partial | not_found), values with their unit and
        source id, citations in sources (each a quote fused to its section_id, document_id, sizes), and the
        reasoning that says how the verdict was reached. Every value points into sources; file links the human to
        the original document.

        Follow-ups go through get_section and get_document with the handles the answer carries, not through a
        second ask.

        The library is Italian: quotes come back as found, untranslated.

        A real ask can run minutes; the call just waits.
        """)]
    public async Task<CallToolResult> Ask(CancellationToken cancellationToken, string? question = null)
    {
        if (string.IsNullOrWhiteSpace(question))
            return Results.Error("The question is missing: ask takes the user's question, self-contained, as spoken.");

        var result = await handler.AskAsync(question.Trim(), cancellationToken);

        return Results.Answer(new AskResponse(
            result.Id,
            result.Question,
            AskHandler.Wire(result.Status),
            result.Reasoning,
            [.. result.Values.Select(value => new AskValue(value.Name, value.Value, value.Unit, value.Source))],
            [.. result.Sources.Select(source => new AskSource(
                source.Id, source.DocumentId, source.Kind, source.Section, source.SectionId,
                source.Quote, source.SectionChars, source.DocumentChars, source.File))],
            result.CompletedAt));
    }
}
