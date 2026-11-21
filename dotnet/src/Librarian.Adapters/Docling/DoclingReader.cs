using System.Net.Http.Headers;
using System.Text.Json.Nodes;
using Librarian.Application.Ports.Ingest;

namespace Librarian.Adapters.Docling;

public sealed class DoclingReader(IHttpClientFactory httpClientFactory) : IDocumentReader
{
    public async Task<IReadOnlyList<Page>> ReadAsync(string path, CancellationToken cancellationToken)
    {
        var client = httpClientFactory.CreateClient("doclingReader");
        using var content = new MultipartFormDataContent();
        await using var stream = File.OpenRead(path);
        using var fileContent = new StreamContent(stream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/pdf");
        content.Add(fileContent, "files", Path.GetFileName(path));
        content.Add(new StringContent("json"), "to_formats");
        content.Add(new StringContent("false"), "do_ocr");

        using var response = await client.PostAsync("v1/convert/file", content, cancellationToken);
        response.EnsureSuccessStatusCode();
        var payload = await JsonNode.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken), cancellationToken: cancellationToken)
            ?? throw new InvalidOperationException("docling-serve returned an empty response.");

        return DoclingJson.ToPages(payload["document"]?["json_content"]
            ?? throw new InvalidOperationException("docling-serve returned no json_content."));
    }
}

internal static class DoclingJson
{
    public static IReadOnlyList<Page> ToPages(JsonNode document)
    {
        var texts = document["texts"]?.AsArray();
        var tables = document["tables"]?.AsArray();
        var groups = document["groups"]?.AsArray();
        var buckets = new SortedDictionary<int, List<string>>();

        Walk(document["body"], inPicture: false);
        var pageCount = Math.Max(
            document["pages"]?.AsObject().Count ?? 0,
            buckets.Count == 0 ? 0 : buckets.Keys.Max());
        var pages = new List<Page>(pageCount);
        for (var number = 1; number <= pageCount; number++)
            pages.Add(new Page(number, buckets.TryGetValue(number, out var parts) ? string.Join("\n\n", parts) : ""));
        return pages;

        void Walk(JsonNode? node, bool inPicture)
        {
            if (node?["children"] is not JsonArray children)
                return;
            foreach (var child in children)
            {
                var reference = child?["$ref"]?.GetValue<string>() ?? "";
                if (reference.StartsWith("#/texts/", StringComparison.Ordinal) && texts is not null)
                {
                    var item = texts[int.Parse(reference["#/texts/".Length..])];
                    var text = item?["text"]?.GetValue<string>();
                    if (!inPicture && item?["content_layer"]?.GetValue<string>() == "body" && text is not null)
                        Add(item, text);
                }
                else if (reference.StartsWith("#/tables/", StringComparison.Ordinal) && tables is not null)
                {
                    if (!inPicture)
                        Add(tables[int.Parse(reference["#/tables/".Length..])], RenderTable(tables[int.Parse(reference["#/tables/".Length..])]!));
                }
                else if (reference.StartsWith("#/groups/", StringComparison.Ordinal) && groups is not null)
                {
                    Walk(groups[int.Parse(reference["#/groups/".Length..])], inPicture);
                }
                else if (reference.StartsWith("#/pictures/", StringComparison.Ordinal))
                {

                }
            }
        }

        void Add(JsonNode? item, string markdown)
        {
            var page = item?["prov"]?[0]?["page_no"]?.GetValue<int>() ?? 1;
            if (!buckets.TryGetValue(page, out var parts))
                buckets[page] = parts = [];
            parts.Add(markdown);
        }
    }

    private static string RenderTable(JsonNode table)
    {
        var data = table["data"] ?? throw new InvalidOperationException("docling table has no data.");
        var rows = data["num_rows"]?.GetValue<int>() ?? throw new InvalidOperationException("docling table has no num_rows.");
        var cols = data["num_cols"]?.GetValue<int>() ?? throw new InvalidOperationException("docling table has no num_cols.");
        var grid = Enumerable.Range(0, rows).Select(_ => new string[cols]).ToArray();
        foreach (var cell in data["table_cells"]?.AsArray() ?? [])
        {
            var row = cell?["row"]?.GetValue<int>() ?? 0;
            var col = cell?["col"]?.GetValue<int>() ?? 0;
            if (row < rows && col < cols)
                grid[row][col] = cell?["text"]?.GetValue<string>()?.Replace("\n", " ").Trim() ?? "";
        }
        var lines = grid.Select(r => "| " + string.Join(" | ", r) + " |").ToList();
        if (lines.Count > 1)
            lines.Insert(1, "| " + string.Join(" | ", Enumerable.Repeat("---", cols)) + " |");
        return string.Join("\n", lines);
    }
}
