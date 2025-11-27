f"""
Simple configuration for trading signals prompts and system settings.
All prompts and templates in one place for MVP.
"""

import os

# Function to get ACTIVE_PROMPT dynamically (reads env var each time)
# DEFAULT is 'signals' - digest format is DEPRECATED and should never be used
def get_active_prompt():
    """Get the current ACTIVE_PROMPT setting from environment.
    
    Returns 'signals' by default. The 'digest' format is DEPRECATED.
    """
    prompt = os.getenv('ACTIVE_PROMPT', 'signals')
    # Enforce signals - digest is deprecated
    if prompt == 'digest':
        import warnings
        warnings.warn(
            "DIGEST format is DEPRECATED and should not be used. "
            "Defaulting to 'signals'. Set ACTIVE_PROMPT=signals explicitly.",
            DeprecationWarning,
            stacklevel=2
        )
        return 'signals'
    return prompt

# For backward compatibility, provide ACTIVE_PROMPT as a property
# But it will read dynamically each time
class ActivePrompt:
    """Dynamic ACTIVE_PROMPT that reads environment variable at access time."""
    def __str__(self):
        return get_active_prompt()
    
    def __repr__(self):
        return f"'{get_active_prompt()}'"
    
    def __eq__(self, other):
        return str(self) == str(other)
    
    def __ne__(self, other):
        return str(self) != str(other)

ACTIVE_PROMPT = ActivePrompt()


SIGNALS_MESSAGE = """You're generating trading signals for Leviathan News - the edgy crypto publication that gives traders actionable alpha. Your audience is crypto natives who want clear, actionable trading signals based on recent news.

Tracked Tokens:
{token_list}

Recent Headlines:
{headlines}

Generate concise trading signals in this exact format:

**[Token Symbol] [Token Name]: [SIGNAL]** - [One sentence reason] ([more info](LINK))

SIGNAL TYPES (use exactly these labels):
- STRONG BUY: High conviction buy opportunity based on news
- BUY: Positive signal worth considering
- WEAK BUY: Slight positive signal, lower priority
- WEAK SELL: Slight negative signal
- SELL: Clear negative signal
- STRONG SELL: High conviction sell signal

**CRITICAL RULES:**
1. ONLY analyze tokens that appear in BOTH the tracked tokens list AND the recent headlines
2. ONLY generate signals when there is an actual news-driven catalyst - if there's no relevant news for a token, skip it entirely
3. NEVER generate signals for stablecoins (USDC, USDT, DAI, FRAX, crvUSD, etc.) - they're designed to be stable
4. Match tokens by their symbol (e.g., $BTC, $ETH, $AAVE) or name mentioned in headlines
5. READ THE HEADLINES CAREFULLY - base your signals on what the news ACTUALLY says, not general market sentiment
6. Format links as markdown: ([more info](URL)) - the URL should be clickable text, not visible
7. Keep each signal to ONE concise sentence explaining the reasoning based on what the news actually says
8. Be opinionated and direct - no hedging or disclaimers
9. Focus on actionable signals, not general market commentary
10. NO CITATIONS like [1], [2] - use the format ([more info](URL)) instead
11. Order signals by conviction strength (STRONG BUY first, then BUY, etc.)
12. If a token has no meaningful news catalyst, DO NOT generate a signal - silence is better than noise
13. NEVER mention tokens that you didn't generate signals for - if there's no signal, don't mention the token at all
14. ONLY output trading signals - NO other sections, NO "Market Context", NO commentary, NO headers, NO separators - JUST the signals, one per line
15. Each signal MUST be on its own separate line - never put multiple signals on the same line

Example format (notice: ONLY list tokens with signals, never mention skipped tokens):
**$BTC Bitcoin: STRONG BUY** - Recent leverage cascade created a rare buying opportunity for blue chips ([more info](https://example.com/article1))
**$ETH Ethereum: WEAK BUY** - Prioritize Bitcoin first but solid secondary allocation if portfolio has room ([more info](https://example.com/article2))
**$AAVE Aave: SELL** - Critical vulnerability discovered in lending contracts, exit positions until patched ([more info](https://example.com/article3))

Be sharp, direct, and actionable. Only generate signals when there's real alpha. No fluff, no disclaimers, no fake signals."""

SIGNALS_MESSAGE_FALLBACK = """You're generating trading signals for Leviathan News. Your audience is crypto traders who need actionable signals even from subtle news catalysts.

Tracked Tokens:
{token_list}

Recent Headlines:
{headlines}

Generate trading signals in this exact format:

**[Token Symbol] [Token Name]: [SIGNAL]** - [One sentence reason] ([more info](LINK))

SIGNAL TYPES:
- STRONG BUY: High conviction buy
- BUY: Positive signal
- WEAK BUY: Slight positive signal
- WEAK SELL: Slight negative signal
- SELL: Clear negative signal
- STRONG SELL: High conviction sell

IMPORTANT RULES:
1. You MUST generate at least 3-5 signals for today - traders need actionable direction
2. Analyze news that mentions any tracked tokens - be more inclusive than strict
3. Use subtle catalysts: technical upgrades, partnerships, regulatory news, ecosystem growth
4. WEAK BUY/WEAK SELL signals are acceptable for minor catalysts - provide nuanced viewpoint
5. If a token appears in headlines at all, it deserves at least a WEAK signal
6. Format: **$SYMBOL Token Name: SIGNAL** - reason ([more info](URL))
7. One signal per line, no headers, no commentary, just signals
8. Order by conviction: STRONG BUY first, then BUY, then WEAK signals

Example (more inclusive than strict mode):
**$ETH Ethereum: WEAK BUY** - Gas optimization proposals keep improving scalability ([more info](URL))
**$MON Monad: BUY** - Continued ecosystem momentum with new DeFi protocols ([more info](URL))

Generate actionable signals. Even with modest catalysts, provide direction to traders."""

DIGEST_MESSAGE = """You're writing for Leviathan News - the edgy, irreverent crypto publication that cuts through the BS. Your audience is crypto natives who want alpha, not corporate fluff.

Headlines:
{headlines}

Write a crypto analysis in this style:

**Lead Story Deep Dive** - Pick the most interesting story and explain what's REALLY happening behind the headline. Add context, background, and why it matters. Don't just summarize - explain the angles most people miss.

**Other Trends We Noticed** - Group related stories and explain the bigger picture. What's the narrative? Why should people care? Add your take on what's driving these trends.

**Under the Radar** - Highlight stories that didn't make the top 5 but deserve attention. Explain why they're interesting and what they signal.

**Key Points:**
- Add context beyond what's in headlines
- Explain WHY things matter, not just WHAT happened  
- Use insider knowledge and background
- Be opinionated but informative
- Write like you're explaining to a smart friend who missed the news
- No generic sections or redundant analysis
- Focus on stories readers can actually see in the top 5
- NO CITATIONS OR SOURCE REFERENCES - don't use [1], [2], etc.

Channel that Leviathan voice - sharp, contextual, and always adding value beyond the obvious."""


prompts = {'signals': SIGNALS_MESSAGE, 'signals_fallback': SIGNALS_MESSAGE_FALLBACK, 'digest': DIGEST_MESSAGE}

# Function to get SYSTEM_MESSAGE dynamically based on current ACTIVE_PROMPT
# This ensures it reads the environment variable at call time, not import time
def get_system_message():
    """Get the system message for the current ACTIVE_PROMPT setting.
    
    Always returns signals prompt - digest format is DEPRECATED.
    """
    current_prompt = get_active_prompt()
    # Only allow signals - digest is deprecated
    if current_prompt != 'signals':
        import warnings
        warnings.warn(
            f"ACTIVE_PROMPT='{current_prompt}' is not supported. Using 'signals' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        current_prompt = 'signals'
    return prompts.get(current_prompt, prompts['signals'])

# For backward compatibility, create a class that behaves like a string
# but reads ACTIVE_PROMPT dynamically each time it's accessed
class SystemMessage:
    """Dynamic system message that reads ACTIVE_PROMPT at access time."""
    def __str__(self):
        return get_system_message()
    
    def __repr__(self):
        return f"<SystemMessage: {get_system_message()[:50]}...>"
    
    def format(self, **kwargs):
        return get_system_message().format(**kwargs)

SYSTEM_MESSAGE = SystemMessage()


def get_fallback_system_message():
    """Get fallback signal message when initial generation produces zero signals.

    This more inclusive prompt is used for retry when the strict prompt
    produces no signals despite having news and tokens available.
    """
    return prompts.get('signals_fallback', SIGNALS_MESSAGE_FALLBACK)