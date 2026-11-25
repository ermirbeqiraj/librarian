using System.ComponentModel;
using Application.Handlers.Serve;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

namespace Api.Mcp.GetSection;

[McpServerToolType]
internal sealed class GetSectionTool(ServeHandler serve)
{
    [McpServerTool(ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("""
        Pull one section's full text, uncut — exactly the section_chars its citation signposted. Takes the
        section_id a citation or a document map carries.

        The answer: the section's heading, its position of the document's sections, the document_id and kind it
        belongs to, the text itself, and the file link to the original document.

        Plain reading: no ask spent, nothing trimmed, no markers.
        """)]
    public async Task<CallToolResult> GetSection(CancellationToken cancellationToken, long? section_id = null)
    {
        if (section_id is not { } id)
            return Results.Error("The section_id is missing: get_section takes the section_id a citation carries.");

        var pull = await serve.PullAsync(id, cancellationToken);

        return pull is null
            ? Results.Error($"No section with section_id {id}.")
            : Results.Answer(new GetSectionResponse(
                pull.SectionId, pull.DocumentId, pull.Kind, pull.Heading,
                pull.Position, pull.Of, pull.Text, pull.File));
    }
}
