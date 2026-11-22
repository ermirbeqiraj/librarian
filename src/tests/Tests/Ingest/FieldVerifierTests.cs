using Application.Handlers.Ingest.Extract;

namespace Tests.Ingest;

public sealed class FieldVerifierTests
{
    [Fact]
    public void Found_ignores_spaces_and_line_breaks()
    {
        var text = "Totale da pagare:\n1.234,56 €\n(s already paid)";
        Assert.True(FieldVerifier.FoundIn(text, "1.234,56 €"));
        Assert.True(FieldVerifier.FoundIn(text, "Totale\nda\npagare:"));
        Assert.False(FieldVerifier.FoundIn(text, "1.234,57 €"));
    }

    [Fact]
    public void Found_is_case_sensitive()
    {
        Assert.False(FieldVerifier.FoundIn("INTESA SANPAOLO", "intesa sanpaolo"));
    }

    [Fact]
    public void A_null_as_written_or_value_from_the_model_is_not_found_and_not_well_formed()
    {
        Assert.False(FieldVerifier.FoundIn("some text", null));
        Assert.False(FieldVerifier.WellFormed(FieldKind.Date, null));
        Assert.False(FieldVerifier.WellFormed(FieldKind.Number, null));
    }

    [Theory]
    [InlineData(FieldKind.Date, "2026-09-01", true)]
    [InlineData(FieldKind.Date, "2026-02-30", false)]
    [InlineData(FieldKind.Date, "01/09/2026", false)]
    [InlineData(FieldKind.Number, "1234.56", true)]
    [InlineData(FieldKind.Number, "-12.5", true)]
    [InlineData(FieldKind.Number, "1.234,56", false)]
    [InlineData(FieldKind.Number, "12 €", false)]
    [InlineData(FieldKind.Text, "anything at all", true)]
    public void WellFormed_checks_the_kind(FieldKind kind, string value, bool expected)
    {
        Assert.Equal(expected, FieldVerifier.WellFormed(kind, value));
    }

    [Fact]
    public void Check_reports_not_found_with_the_fix()
    {
        var draft = new ExtractDraft("invoice", new ValidityDraft("2026-09-01", "", "del 01/09/2026"),
            "a bill", [new FieldDraft("total_amount", "10.00", "10,00 €", FieldKind.Number)]);
        var report = FieldVerifier.Check(draft, "Fattura n. 5 del 01/09/2026, totale 10,00 €");
        var field = Assert.Single(report.Checks, c => c.Name == "total_amount");
        Assert.True(field.Found);
        Assert.True(field.WellFormed);
        var validity = Assert.Single(report.Checks, c => c.Name == "validity");
        Assert.True(validity.Found);
        Assert.True(validity.WellFormed);

        var missing = FieldVerifier.Check(draft, "Fattura n. 5");
        var missingField = Assert.Single(missing.Checks, c => c.Name == "total_amount");
        Assert.False(missingField.Found);
        Assert.Contains("not in the text", missingField.Message);
    }
}
