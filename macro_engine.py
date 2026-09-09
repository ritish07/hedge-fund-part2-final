# macro_engine.py
"""
Global Macro & Geopolitical Intelligence Desk for Autonomous AI Hedge Fund.
Aggregates:
- Real-time Intermarket Benchmarks (US 10Y Yield, WTI Crude Oil, DXY, Gold, Bitcoin)
- Breaking Global Financial & Geopolitical News (Forex, Central Banks, Tariffs, Conflicts)
- Trading Session Context (Tokyo / London / New York)
- DeepSeek Macro Synthesis: Regime, Geopolitical Threat Level, Gold/BTC/Forex biases.
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import requests
import config

MACRO_STATE_FILE = Path(__file__).with_name("macro_state.json")
CACHE_TTL_SECONDS = 900  # 15 minutes

# In-memory cache
_cached_macro: Dict[str, Any] = {}
_last_fetch_time: float = 0.0

DEFAULT_INTERMARKET = {
    "^TNX": {"name": "US 10Y Yield", "price": 4.80, "change_pct": 0.0},
    "CL=F": {"name": "WTI Crude Oil", "price": 94.0, "change_pct": 0.0},
    "DX-Y.NYB": {"name": "US Dollar Index", "price": 98.8, "change_pct": 0.0},
    "GC=F": {"name": "Gold Futures", "price": 4420.0, "change_pct": 0.0},
    "BTC-USD": {"name": "Bitcoin", "price": 78900.0, "change_pct": 0.0},
}

DEFAULT_MACRO_STATE: Dict[str, Any] = {
    "geopolitical_risk_level": "MODERATE",
    "market_regime": "NEUTRAL",
    "fed_rate_stance": "NEUTRAL",
    "active_session": "GLOBAL",
    "session_sentiment": "Global markets trading in standard ranges across major currency pairs.",
    "us_10y_yield": 4.80,
    "crude_oil_price": 94.0,
    "dxy_bias": "NEUTRAL",
    "gold_bias": "NEUTRAL",
    "gold_rationale": "Balanced between elevated yields and geopolitical uncertainty.",
    "bitcoin_bias": "NEUTRAL",
    "bitcoin_rationale": "Trading in macro consolidation awaiting liquidity catalysts.",
    "forex_bias": "Major forex pairs reflecting central bank rate differentials.",
    "top_bulletins": [
        "Global central banks navigating inflation and economic growth balance",
        "Geopolitical trade and regional flashpoints remain in focus",
        "Energy markets steady amid OPEC+ production monitors"
    ],
    "intermarket": DEFAULT_INTERMARKET,
    "last_updated": datetime.now(timezone.utc).isoformat()
}


def get_current_session() -> Dict[str, str]:
    """Determine the active forex/global trading session based on current UTC hour."""
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour

    if 0 <= hour < 7:
        session = "TOKYO / ASIAN"
        desc = "Asian Session (Tokyo, Hong Kong, Sydney) active."
    elif 7 <= hour < 12:
        session = "LONDON / EUROPEAN"
        desc = "London/European Session active with primary forex volume."
    elif 12 <= hour < 16:
        session = "LONDON / NEW YORK OVERLAP"
        desc = "Peak global liquidity: London & New York both open."
    elif 16 <= hour < 21:
        session = "NEW YORK AFTERNOON"
        desc = "New York Session dominating dollar and equity flows."
    else:
        session = "SYDNEY / PRE-ASIA"
        desc = "Pacific/Early Asian twilight session."

    return {"session": session, "description": desc, "utc_time": now_utc.strftime("%H:%M UTC")}


def fetch_intermarket_benchmarks() -> Dict[str, Any]:
    """
    Fetch live benchmark quotes (US 10Y Yield, WTI Crude Oil, DXY, Gold, Bitcoin)
    using Yahoo Finance v8 chart API.
    """
    tickers = {
        "^TNX": "US 10Y Yield",
        "CL=F": "WTI Crude Oil",
        "DX-Y.NYB": "US Dollar Index",
        "GC=F": "Gold Futures",
        "BTC-USD": "Bitcoin",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    results = {}

    for sym, name in tickers.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                meta = res.json()["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice")
                prev = meta.get("chartPreviousClose")
                chg = ((price - prev) / prev * 100) if (price and prev) else 0.0
                results[sym] = {
                    "name": name,
                    "price": round(float(price), 3) if price else DEFAULT_INTERMARKET[sym]["price"],
                    "change_pct": round(float(chg), 2)
                }
            else:
                results[sym] = DEFAULT_INTERMARKET[sym]
        except Exception:
            results[sym] = DEFAULT_INTERMARKET[sym]

    return results


def fetch_breaking_headlines() -> List[str]:
    """
    Fetch and clean live financial & geopolitical headlines from top RSS newsfeeds.
    """
    feed_urls = [
        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.investing.com/rss/forex.rss",
        "https://www.investing.com/rss/news_25.rss",
        "https://cointelegraph.com/rss",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    headlines = []

    for url in feed_urls:
        try:
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for item in root.findall(".//item")[:4]:
                    title_elem = item.find("title")
                    if title_elem is not None and title_elem.text:
                        text = title_elem.text.strip()
                        # Clean up HTML entities or weird chars
                        text = re.sub(r"<[^>]+>", "", text)
                        if len(text) > 15 and text not in headlines:
                            headlines.append(text)
        except Exception:
            continue

    return headlines[:15]


def synthesize_macro_intelligence(intermarket: Dict[str, Any], headlines: List[str]) -> Dict[str, Any]:
    """
    Calls DeepSeek to synthesize raw headlines, session context, and intermarket
    prices into an institutional Global Macro Intelligence Dossier.
    """
    session_info = get_current_session()

    # Format text for prompt
    intermarket_str = "\n".join(
        f"- {info['name']} ({sym}): {info['price']} ({info['change_pct']:+0.2f}%)"
        for sym, info in intermarket.items()
    )

    headlines_str = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:10]))
    if not headlines_str:
        headlines_str = "Global central banks monitor inflation prints; trade and geopolitical updates steady."

    prompt = f"""You are the Chief Global Macro Strategist and Geopolitical Risk Officer for a quantitative hedge fund.

Current Session: {session_info['session']} ({session_info['utc_time']}) - {session_info['description']}

LIVE INTERMARKET BENCHMARK DATA:
{intermarket_str}

LIVE BREAKING HEADLINES & MARKET WRAPS:
{headlines_str}

Analyze this live intelligence to establish current macro regimes, geopolitical threats, Fed policy posture, and direct asset impacts (especially on Gold, Bitcoin, and Forex).

Return ONLY a JSON object strictly conforming to this schema:
{{
  "geopolitical_risk_level": "LOW" | "MODERATE" | "ELEVATED" | "CRITICAL",
  "market_regime": "RISK_ON" | "RISK_OFF" | "STAGFLATION_CONCERN" | "NEUTRAL",
  "fed_rate_stance": "HAWKISH" | "DOVISH" | "NEUTRAL",
  "dxy_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "session_sentiment": "1 sentence describing current trading session tone and catalyst",
  "gold_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "gold_rationale": "1-2 sentences on how bond yields, DXY, and geopolitical conflicts impact Gold right now",
  "bitcoin_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "bitcoin_rationale": "1-2 sentences on how macro liquidity and risk appetite impact Bitcoin right now",
  "forex_bias": "1-2 sentences on major currency moves (USD, JPY, EUR, CAD) including oil price impact on CAD",
  "top_bulletins": [
    "Most critical headline/catalyst 1 (e.g. Fed/rate statement or war/geopolitical event)",
    "Most critical headline/catalyst 2 (e.g. Trump/tariffs, China, or inflation print)",
    "Most critical headline/catalyst 3 (e.g. Oil/energy shock or Yen carry unwind)"
  ]
}}
"""

    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=25,
        )
        response.raise_for_status()
        parsed = json.loads(response.json()["choices"][0]["message"]["content"])

        # Construct full state
        macro_state = {
            "geopolitical_risk_level": str(parsed.get("geopolitical_risk_level", "MODERATE")).upper(),
            "market_regime": str(parsed.get("market_regime", "NEUTRAL")).upper(),
            "fed_rate_stance": str(parsed.get("fed_rate_stance", "NEUTRAL")).upper(),
            "active_session": session_info["session"],
            "session_sentiment": str(parsed.get("session_sentiment", "")),
            "us_10y_yield": intermarket.get("^TNX", {}).get("price", 4.80),
            "crude_oil_price": intermarket.get("CL=F", {}).get("price", 94.0),
            "dxy_bias": str(parsed.get("dxy_bias", "NEUTRAL")).upper(),
            "gold_bias": str(parsed.get("gold_bias", "NEUTRAL")).upper(),
            "gold_rationale": str(parsed.get("gold_rationale", "")),
            "bitcoin_bias": str(parsed.get("bitcoin_bias", "NEUTRAL")).upper(),
            "bitcoin_rationale": str(parsed.get("bitcoin_rationale", "")),
            "forex_bias": str(parsed.get("forex_bias", "")),
            "top_bulletins": parsed.get("top_bulletins", []),
            "intermarket": intermarket,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        return macro_state

    except Exception as err:
        print(f"[MACRO ENGINE] DeepSeek synthesis error: {err}. Using fallback.")
        fallback = dict(DEFAULT_MACRO_STATE)
        fallback["intermarket"] = intermarket
        fallback["active_session"] = session_info["session"]
        fallback["last_updated"] = datetime.now(timezone.utc).isoformat()
        return fallback


def save_macro_state(state: Dict[str, Any]) -> None:
    """Save the macro state to disk."""
    try:
        temp_file = MACRO_STATE_FILE.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        temp_file.replace(MACRO_STATE_FILE)
    except Exception as e:
        print(f"[MACRO ENGINE] Failed to save {MACRO_STATE_FILE}: {e}")


def load_macro_state_from_disk() -> Dict[str, Any]:
    """Load cached macro state from disk if available."""
    if not MACRO_STATE_FILE.exists():
        return dict(DEFAULT_MACRO_STATE)
    try:
        with MACRO_STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULT_MACRO_STATE)


def refresh_macro_context() -> Dict[str, Any]:
    """Force an immediate refresh of intermarket benchmarks, news, and LLM synthesis."""
    global _cached_macro, _last_fetch_time

    print("[MACRO ENGINE] Refreshing global intermarket data and breaking headlines...", flush=True)
    intermarket = fetch_intermarket_benchmarks()
    headlines = fetch_breaking_headlines()
    state = synthesize_macro_intelligence(intermarket, headlines)

    _cached_macro = state
    _last_fetch_time = time.time()
    save_macro_state(state)
    print(
        f"[MACRO ENGINE] Intelligence refreshed: Regime={state['market_regime']} | "
        f"Geopolitics={state['geopolitical_risk_level']} | Gold={state['gold_bias']} | BTC={state['bitcoin_bias']}",
        flush=True
    )
    return state


def get_macro_context(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get the current macro intelligence context.
    Uses memory/disk cache if within TTL (15 mins), otherwise refreshes.
    """
    global _cached_macro, _last_fetch_time

    now = time.time()
    if not force_refresh and _cached_macro and (now - _last_fetch_time < CACHE_TTL_SECONDS):
        return _cached_macro

    if not force_refresh and not _cached_macro:
        disk_state = load_macro_state_from_disk()
        # If disk state is fresh enough (within 30 mins), use it
        try:
            last_dt = datetime.fromisoformat(disk_state.get("last_updated", "2000-01-01T00:00:00+00:00"))
            age_sec = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age_sec < CACHE_TTL_SECONDS:
                _cached_macro = disk_state
                _last_fetch_time = now - age_sec
                return _cached_macro
        except Exception:
            pass

    return refresh_macro_context()


if __name__ == "__main__":
    res = refresh_macro_context()
    print(json.dumps(res, indent=2))
