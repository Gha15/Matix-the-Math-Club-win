using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace MatixTheMathClub.Ai;

public sealed class MatixAi
{
    private static readonly HttpClient Http = new();
    private static readonly Regex HtmlTagRegex = new("<[^>]+>", RegexOptions.Compiled);
    private static readonly Regex GoogleLinkRegex = new("<a[^>]+href=\"/url\\?q=([^\"&]+)[^\"]*\"", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex GoogleTitleRegex = new("<h3[^>]*>([\\s\\S]*?)</h3>", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex GoogleSnippetRegex = new("<div[^>]+class=\"(?:BNeawe|VwiC3b|s3v9rd)[^\"]*\"[^>]*>([\\s\\S]*?)</div>", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    public async Task<string> SearchAsync(string query, CancellationToken cancellationToken = default)
    {
        query = query?.Trim() ?? string.Empty;
        if (query.Length == 0)
        {
            return string.Empty;
        }

        if (TryEvaluateArithmetic(query, out var value))
        {
            return FormatNumber(value);
        }

        var google = await GoogleAsync(query, cancellationToken).ConfigureAwait(false);
        if (!string.IsNullOrWhiteSpace(google))
        {
            return google;
        }

        return await DuckAsync(query, cancellationToken).ConfigureAwait(false);
    }

    private static async Task<string> GoogleAsync(string query, CancellationToken cancellationToken)
    {
        var url = $"https://www.google.com/search?q={Uri.EscapeDataString(query)}&num=10&hl=en&gbv=1";
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.TryAddWithoutValidation("User-Agent", "Mozilla/5.0");

        using var response = await Http.SendAsync(request, cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
        {
            return string.Empty;
        }

        var html = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        var link = DecodeGoogleLink(html) ?? url;
        var title = StripHtml(GoogleTitleRegex.Match(html).Groups[1].Value);
        var snippet = StripHtml(GoogleSnippetRegex.Match(html).Groups[1].Value);

        if (snippet.Length == 0)
        {
            return string.Empty;
        }

        if (title.Length == 0)
        {
            title = query;
        }

        return $"{title}\n{snippet}\n{link}";
    }

    private static async Task<string> DuckAsync(string query, CancellationToken cancellationToken)
    {
        try
        {
            var url = $"https://api.duckduckgo.com/?format=json&no_html=1&skip_disambig=1&t=matix&q={Uri.EscapeDataString(query)}";
            using var response = await Http.GetAsync(url, cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return string.Empty;
            }

            await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
            using var doc = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken).ConfigureAwait(false);

            var root = doc.RootElement;
            var heading = root.TryGetProperty("Heading", out var h) ? h.GetString() ?? query : query;
            var text = root.TryGetProperty("AbstractText", out var a) ? a.GetString() ?? string.Empty : string.Empty;
            if (text.Length == 0 && root.TryGetProperty("Answer", out var ans))
            {
                text = ans.GetString() ?? string.Empty;
            }

            if (text.Length == 0)
            {
                return string.Empty;
            }

            var link = root.TryGetProperty("AbstractURL", out var u) ? u.GetString() ?? string.Empty : string.Empty;
            return link.Length == 0 ? $"{heading}\n{text}" : $"{heading}\n{text}\n{link}";
        }
        catch (Exception) when (!cancellationToken.IsCancellationRequested)
        {
            return string.Empty;
        }
    }

    private static bool TryEvaluateArithmetic(string input, out double result)
    {
        result = 0;
        if (string.IsNullOrWhiteSpace(input))
        {
            return false;
        }

        List<Token> tokens;
        try
        {
            tokens = Tokenize(NormalizeArithmeticInput(input));
        }
        catch (FormatException)
        {
            return false;
        }

        if (tokens.Count == 0)
        {
            return false;
        }

        var parser = new Parser(tokens);
        try
        {
            result = parser.ParseExpression();
            return parser.AtEnd;
        }
        catch (FormatException)
        {
            return false;
        }
    }

    private static string NormalizeArithmeticInput(string input)
    {
        var text = input.Trim();
        text = Regex.Replace(text, @"^(?:what\s+is|what's|whats|calculate|compute|solve)\s+", "", RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"[?!.]+$", "");
        return text;
    }

    private static List<Token> Tokenize(string input)
    {
        var tokens = new List<Token>();
        var text = input.Replace('×', '*').Replace('÷', '/').Replace('−', '-').Trim();

        for (var i = 0; i < text.Length;)
        {
            var ch = text[i];
            if (char.IsWhiteSpace(ch))
            {
                i++;
                continue;
            }

            if (char.IsDigit(ch) || ch == '.')
            {
                var start = i;
                i++;
                while (i < text.Length && (char.IsDigit(text[i]) || text[i] == '.'))
                {
                    i++;
                }

                var slice = text[start..i];
                if (!double.TryParse(slice, NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                {
                    throw new FormatException("Invalid number.");
                }

                tokens.Add(new Token(TokenType.Number, number));
                continue;
            }

            if (char.IsLetter(ch))
            {
                var start = i;
                i++;
                while (i < text.Length && char.IsLetter(text[i]))
                {
                    i++;
                }

                var word = text[start..i].ToLowerInvariant();
                tokens.Add(word switch
                {
                    "of" => new Token(TokenType.Of),
                    "percent" => new Token(TokenType.Percent),
                    _ => throw new FormatException("Not a math expression.")
                });
                continue;
            }

            if (ch == '*' && i + 1 < text.Length && text[i + 1] == '*')
            {
                tokens.Add(new Token(TokenType.Power));
                i += 2;
                continue;
            }

            tokens.Add(ch switch
            {
                '+' => new Token(TokenType.Plus),
                '-' => new Token(TokenType.Minus),
                '*' => new Token(TokenType.Star),
                '/' => new Token(TokenType.Slash),
                '^' => new Token(TokenType.Power),
                '%' => new Token(TokenType.Percent),
                '(' => new Token(TokenType.LeftParen),
                ')' => new Token(TokenType.RightParen),
                _ => throw new FormatException("Unknown token.")
            });
            i++;
        }

        return tokens;
    }

    private static string? DecodeGoogleLink(string html)
    {
        var match = GoogleLinkRegex.Match(html);
        if (!match.Success)
        {
            return null;
        }

        var encoded = match.Groups[1].Value;
        return encoded.Length == 0 ? null : Uri.UnescapeDataString(encoded);
    }

    private static string StripHtml(string html)
    {
        if (string.IsNullOrWhiteSpace(html))
        {
            return string.Empty;
        }

        var noTags = HtmlTagRegex.Replace(html, " ");
        return WebUtility.HtmlDecode(noTags).Replace('\n', ' ').Replace('\r', ' ').Trim();
    }

    private static string FormatNumber(double value)
    {
        var rounded = Math.Round(value);
        if (Math.Abs(value - rounded) < 1e-12)
        {
            return rounded.ToString(CultureInfo.InvariantCulture);
        }

        return value.ToString("0.############", CultureInfo.InvariantCulture);
    }

    private readonly record struct Token(TokenType Type, double Number = 0);

    private enum TokenType
    {
        Number,
        Plus,
        Minus,
        Star,
        Slash,
        Power,
        Percent,
        Of,
        LeftParen,
        RightParen
    }

    private sealed class Parser
    {
        private readonly List<Token> _tokens;
        private int _index;

        public Parser(List<Token> tokens)
        {
            _tokens = tokens;
        }

        public bool AtEnd => _index >= _tokens.Count;

        public double ParseExpression()
        {
            var value = ParseTerm();
            while (Match(TokenType.Plus, TokenType.Minus))
            {
                var op = Previous().Type;
                var right = ParseTerm();
                value = op == TokenType.Plus ? value + right : value - right;
            }

            return value;
        }

        private double ParseTerm()
        {
            var value = ParsePower();
            while (Match(TokenType.Star, TokenType.Slash, TokenType.Of))
            {
                var op = Previous().Type;
                var right = ParsePower();
                value = op switch
                {
                    TokenType.Star => value * right,
                    TokenType.Of => value * right,
                    _ => right == 0 ? throw new FormatException("Division by zero.") : value / right
                };
            }

            return value;
        }

        private double ParsePower()
        {
            var left = ParseUnary();
            if (Match(TokenType.Power))
            {
                var right = ParsePower();
                left = Math.Pow(left, right);
            }

            return left;
        }

        private double ParseUnary()
        {
            if (Match(TokenType.Plus))
            {
                return ParseUnary();
            }

            if (Match(TokenType.Minus))
            {
                return -ParseUnary();
            }

            return ParsePrimary();
        }

        private double ParsePrimary()
        {
            if (Match(TokenType.Number))
            {
                var value = Previous().Number;
                while (Match(TokenType.Percent))
                {
                    value /= 100d;
                }

                return value;
            }

            if (Match(TokenType.LeftParen))
            {
                var value = ParseExpression();
                Consume(TokenType.RightParen);
                while (Match(TokenType.Percent))
                {
                    value /= 100d;
                }

                return value;
            }

            throw new FormatException("Expected a number.");
        }

        private void Consume(TokenType expected)
        {
            if (!Check(expected))
            {
                throw new FormatException("Invalid expression.");
            }

            _index++;
        }

        private bool Match(params TokenType[] types)
        {
            foreach (var type in types)
            {
                if (Check(type))
                {
                    _index++;
                    return true;
                }
            }

            return false;
        }

        private bool Check(TokenType type) => !AtEnd && _tokens[_index].Type == type;

        private Token Previous() => _tokens[_index - 1];
    }
}
