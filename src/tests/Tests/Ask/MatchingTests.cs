using System.Text.Json;
using Application.Handlers.Ask;
using Evals.Retrieval;

namespace Tests.Ask;

public sealed class MatchingTests
{
    private static AskedValue Value(decimal number, string? unit = null)
        => new("", JsonDocument.Parse(number.ToString(System.Globalization.CultureInfo.InvariantCulture)).RootElement, unit, 0);

    private static AskedValue Value(string text, string? unit = null)
        => new("", JsonDocument.Parse(JsonSerializer.Serialize(text)).RootElement, unit, 0);

    private static JsonElement Expected(decimal number)
        => JsonDocument.Parse(number.ToString(System.Globalization.CultureInfo.InvariantCulture)).RootElement;

    [Fact]
    public void The_same_plain_number_matches()
    {
        Assert.True(Matching.AnySameValue(Expected(63.33m), "EUR", [Value("63,33 €")]));
        Assert.True(Matching.AnySameValue(Expected(1876.35m), "EUR", [Value("1.876,35")]));
        Assert.True(Matching.AnySameValue(Expected(1876.35m), "EUR", [Value("1,876.35")]));
    }

    [Fact]
    public void Thousands_and_decimals_both_read()
    {
        // 152.000 litri is thousands, 318.746 kWh is a decimal: both readings count.
        Assert.True(Matching.AnySameValue(Expected(152m), "mc", [Value("152000 l", unit: "litri")]));
        Assert.True(Matching.AnySameValue(Expected(318.746m), "kWh", [Value("318.746 kWh")]));
        Assert.True(Matching.AnySameValue(Expected(318746m), "kWh", [Value("318.746 kWh")]));
    }

    [Fact]
    public void Units_convert_to_the_base()
    {
        Assert.True(Matching.AnySameValue(Expected(152m), "mc", [Value("152000", unit: "litri")]));
        Assert.False(Matching.AnySameValue(Expected(152m), "mc", [Value("152000", unit: "kWh")]));
    }

    [Fact]
    public void A_bare_number_takes_the_expected_unit()
    {
        Assert.True(Matching.AnySameValue(Expected(63.33m), "EUR", [Value(63.33m)]));
    }

    [Fact]
    public void A_date_answer_matches_only_as_iso()
    {
        Assert.True(Matching.AnySameValue(JsonDocument.Parse("\"2025-03-15\"").RootElement, null, [Value("2025-03-15")]));
        Assert.False(Matching.AnySameValue(JsonDocument.Parse("\"2025-03-15\"").RootElement, null, [Value("15/03/2025")]));
    }

    [Fact]
    public void A_text_answer_matches_squeezed_and_casefolded()
    {
        Assert.True(Matching.AnySameValue(JsonDocument.Parse(JsonSerializer.Serialize("scontrino")).RootElement, null, [Value("Scontrino")]));
        Assert.True(Matching.AnySameValue(JsonDocument.Parse(JsonSerializer.Serialize("documento di 10 pagine")).RootElement, null, [Value("Documento di 10 Pagine")]));
    }

    [Fact]
    public void A_quote_matches_squeezed_but_complete()
    {
        var passages = new List<AskedPassage> { new("Il canone è di 28,99 € al mese, IVA inclusa.", 0) };
        Assert.True(Matching.ContainsQuote("28,99 € al mese", passages));
        Assert.False(Matching.ContainsQuote("28,99 € all'anno", passages));
    }
}
