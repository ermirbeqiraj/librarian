using Api.Features.Auth;

namespace Tests.Auth;

public sealed class BearerTokenTests
{
    private const string Token = "abcdefghijabcdefghijabcdefghijabcdefghijk";

    [Fact]
    public void The_right_token_matches()
    {
        Assert.True(BearerTokens.Matches(Token, Token));
    }

    [Fact]
    public void A_token_one_character_off_is_refused()
    {
        Assert.False(BearerTokens.Matches(Token, Token[..^1] + "x"));
    }

    [Fact]
    public void A_token_of_a_different_length_is_refused()
    {
        Assert.False(BearerTokens.Matches(Token, Token + "x"));
    }

    [Fact]
    public void A_token_differing_only_in_case_is_refused()
    {
        Assert.False(BearerTokens.Matches(Token, Token.ToUpperInvariant()));
    }
}
