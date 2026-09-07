# ai_brain.py

import json
from pathlib import Path

import requests

import config


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
RULES_FILE = Path(__file__).with_name("new_rules.json")


def load_learned_rules(symbol):
    """Load valid, symbol-specific confidence rules from the daily audit."""

    if not RULES_FILE.exists():
        return []

    try:
        with RULES_FILE.open("r", encoding="utf-8") as rules_file:
            rules_document = json.load(rules_file)
    except (OSError, json.JSONDecodeError):
        return []

    rules = rules_document.get("rules", [])
    if not isinstance(rules, list):
        return []

    valid_rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue

        try:
            reduction = int(rule["confidence_reduction_points"])
            affected_symbol = str(rule["affected_symbol"])
            setup = str(rule["setup"]).strip()
            evidence = str(rule["evidence"]).strip()
        except (KeyError, TypeError, ValueError):
            continue

        if (
            affected_symbol == symbol
            and setup
            and evidence
            and 1 <= reduction <= 50
        ):
            valid_rules.append(
                {
                    "setup": setup,
                    "confidence_reduction_points": reduction,
                    "evidence": evidence,
                    "sample_size": rule.get("sample_size"),
                }
            )

    return valid_rules


def get_ai_decision(market_data, symbol):
    """
    Send multi-timeframe market data to DeepSeek and return
    a structured trading decision.

    Expected market_data format:
    {
        "symbol": "...",
        "daily_csv": "...",
        "hourly_csv": "...",
        "market_context": {"daily": {...}, "h1": {...}},
        "equity": float,
        "ask": float
    }

    Returns:
    {
        "signal": "BUY" | "SELL" | "HOLD",
        "confidence_score": 0-100,
        "logic": "2 sentence explanation",
        "stop_loss": float | null,
        "take_profit": float | null
    }
    """

    learned_rules = load_learned_rules(symbol)
    learned_rules_context = json.dumps(learned_rules, indent=2)

    system_prompt = f"""
You are an elite quantitative trader analyzing {symbol}.

Analyze the provided market data using:
- Daily timeframe for macro trend and major market structure
- H1 timeframe for short-term momentum and price action
- Trend direction
- Higher highs and higher lows
- Lower highs and lower lows
- Momentum
- Potential reversals
- Breakouts and breakdowns
- Overall alignment between the Daily and H1 timeframes
- ATR(14) for current volatility
- RSI(14) for momentum and overbought/oversold conditions
- EMA(200) for the dominant trend
- Relative Volume (current tick volume divided by its 20-period average) for conviction

Risk parameters for BUY or SELL:
- Use the H1 ATR(14) and the current ask price to calculate exact prices.
- BUY: stop_loss = ask - (1.5 * H1 ATR); take_profit = ask + (3.0 * H1 ATR).
- SELL: stop_loss = ask + (1.5 * H1 ATR); take_profit = ask - (3.0 * H1 ATR).
- Return the calculated prices as numbers, rounded sensibly for the instrument.
- HOLD: set both stop_loss and take_profit to null.

Your job is to decide whether the best action RIGHT NOW is BUY, SELL, or HOLD.

Be conservative. If the market structure is unclear, conflicting, or there is no high-quality setup, return HOLD.

LEARNED LOSS-PATTERN RULES
The following rules were generated from repeated, realized losses in prior
trades. For every rule whose setup is present now, reduce confidence_score by
the listed confidence_reduction_points. Do not increase confidence to offset a
rule. If the resulting setup is not high quality, return HOLD.

Applicable rules for {symbol}:
{learned_rules_context}

DEEP MARKET CONTEXT
The indicator values below were calculated from a longer history than the
displayed candles. Use them as primary quantitative context. A null value
means there was insufficient history, so do not infer a value.

Daily indicators: {json.dumps(market_data.get("market_context", {}).get("daily", {}))}
H1 indicators: {json.dumps(market_data.get("market_context", {}).get("h1", {}))}

You MUST return ONLY valid JSON.
Do not include markdown.
Do not include ```json.
Do not include any text before or after the JSON.

Return EXACTLY this structure:

{{
    "signal": "BUY",
    "confidence_score": 85,
    "logic": "Sentence one explaining the market structure. Sentence two explaining why BUY, SELL, or HOLD is the best decision.",
    "stop_loss": 1.08125,
    "take_profit": 1.08425
}}

Rules:
- signal MUST be exactly one of: BUY, SELL, HOLD
- confidence_score MUST be an integer from 0 to 100
- logic MUST contain exactly 2 sentences
- BUY and SELL MUST include numeric stop_loss and take_profit values.
- For BUY: stop_loss < current ask < take_profit. For SELL: take_profit < current ask < stop_loss.
- HOLD MUST set stop_loss and take_profit to null
- Do not add any additional JSON fields
"""

    user_prompt = f"""
Analyze the following live market data for {symbol}.

CURRENT MARKET INFORMATION:
Symbol: {symbol}
Current Ask Price: {market_data.get("ask")}
Account Equity: {market_data.get("equity")}

DAILY TIMEFRAME DATA
This represents the macro trend. The last 10 candles are provided as CSV:

{market_data.get("daily_csv")}

H1 TIMEFRAME DATA
This represents recent micro momentum. The last 24 candles are provided as CSV:

{market_data.get("hourly_csv")}

Based on the Daily and H1 data, determine the best trading action now.
"""

    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.1,
        "response_format": {
            "type": "json_object"
        }
    }

    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        response_data = response.json()

        ai_content = response_data["choices"][0]["message"]["content"]

        # Convert DeepSeek JSON response into Python dictionary
        decision = json.loads(ai_content)

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"DeepSeek API request failed: {e}")

    except KeyError as e:
        raise RuntimeError(
            f"Unexpected DeepSeek API response format. Missing key: {e}"
        )

    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"DeepSeek returned invalid JSON: {e}"
        )

    # ---------------------------------------------------------
    # Validate signal
    # ---------------------------------------------------------

    signal = str(decision.get("signal", "")).upper()

    if signal not in ["BUY", "SELL", "HOLD"]:
        raise ValueError(
            f"Invalid AI signal received: {signal}"
        )

    # ---------------------------------------------------------
    # Validate confidence score
    # ---------------------------------------------------------

    try:
        confidence_score = int(decision.get("confidence_score"))
    except (TypeError, ValueError):
        raise ValueError(
            "AI returned an invalid confidence_score"
        )

    # Keep the score within the required range
    confidence_score = max(0, min(100, confidence_score))

    # ---------------------------------------------------------
    # Validate logic
    # ---------------------------------------------------------

    logic = str(decision.get("logic", "")).strip()

    if not logic:
        raise ValueError(
            "AI returned empty trading logic"
        )

    # ---------------------------------------------------------
    # Validate ATR-derived protection prices
    # ---------------------------------------------------------

    stop_loss = decision.get("stop_loss")
    take_profit = decision.get("take_profit")
    reference_price = float(market_data.get("ask"))

    if signal == "HOLD":
        stop_loss = None
        take_profit = None
    else:
        try:
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            raise ValueError(
                "AI returned invalid ATR-based stop_loss or take_profit"
            )

        if signal == "BUY":
            valid_levels = stop_loss < reference_price < take_profit
        else:
            valid_levels = take_profit < reference_price < stop_loss

        if not valid_levels:
            raise ValueError(
                "AI returned stop_loss/take_profit on the wrong side of price"
            )

    # Return clean, standardized result
    return {
        "signal": signal,
        "confidence_score": confidence_score,
        "logic": logic,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }
