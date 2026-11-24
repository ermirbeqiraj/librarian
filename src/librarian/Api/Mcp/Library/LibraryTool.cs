using System.ComponentModel;
using Application.Handlers.Serve;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

namespace Api.Mcp.Library;

[McpServerToolType]
internal sealed class LibraryTool(ServeHandler serve)
{
    [McpServerTool(ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("""
        See what the library holds, before any ask is spent. No parameters.

        The shelf: the total documents, then one group per kind × issuer — how many documents it holds and the
        validity period they cover; issuer and validity are null where a document has none.

        Use it to name things right in the next question: issuers as they sit in the data, the periods the library
        actually covers.
        """)]
    public async Task<CallToolResult> Library(CancellationToken cancellationToken)
    {
        var shelf = await serve.ShelfAsync(cancellationToken);

        return Results.Answer(new LibraryResponse(
            shelf.Documents,
            [.. shelf.Groups.Select(group => new ShelfGroup(
                group.Kind, group.Issuer, group.Documents,
                group.Validity is null ? null : new ShelfPeriod(group.Validity.From, group.Validity.To)))]));
    }
}
