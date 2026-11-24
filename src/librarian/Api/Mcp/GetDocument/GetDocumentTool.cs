using System.ComponentModel;
using Application.Handlers.Serve;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

namespace Api.Mcp.GetDocument;

[McpServerToolType]
internal sealed class GetDocumentTool(ServeHandler serve)
{
    [McpServerTool(ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("""
        Read a whole document from a document_id alone: the link card and the map, never the document's text.

        The card: kind, a description in the library's own words, the validity it covers, document_chars of what
        the link holds, and the file link to the original.

        The map: every section with its section_id, position and heading — walk the document section by section
        through get_section, no model spend, no ask.
        """)]
    public async Task<CallToolResult> GetDocument(CancellationToken cancellationToken, long? document_id = null)
    {
        if (document_id is not { } id)
            return Results.Error("The document_id is missing: get_document takes the document_id a source carries.");

        var card = await serve.CardAsync(id, cancellationToken);

        return card is null
            ? Results.Error($"No document with document_id {id}.")
            : Results.Answer(new GetDocumentResponse(
                card.DocumentId,
                card.Kind,
                card.Description,
                card.Validity is null
                    ? null
                    : new CardValidity(card.Validity.From, card.Validity.To, card.Validity.AsWritten),
                card.DocumentChars,
                [.. card.Sections
                    .Select(section => new MapEntry(section.SectionId, section.Position, section.Heading))],
                card.File));
    }
}
