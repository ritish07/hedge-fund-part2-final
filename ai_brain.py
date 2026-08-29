import requests
import json
import config

def analyze_market(market_data, symbol="EURUSD"):
    return get_ai_decision(market_data, symbol)

def get_ai_decision(market_data, symbol):
    if not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY.startswith("sk-your"):
        # Mock Response for Testing if no API key is provided
        return {
            "signal": "BUY",
            "confidence_score": 85,
            "logic": f"[{symbol}] The Daily trend is bullish, and 1H structure just broke above a major resistance level. Momentum is strong."
        }
    
    base_url = getattr(config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
    You are an elite quant trader analyzing {symbol}. Analyze the macro and micro market structure (higher highs, support/resistance).
    Do not use generic indicators. Based purely on price action, return your decision in EXACTLY this JSON format:
    {{
        "signal": "BUY",  // Can be BUY, SELL, or HOLD
        "confidence_score": 85, // 0 to 100
        "logic": "2 sentences explaining your exact reasoning based on market structure"
    }}
    """

    daily = market_data.get("daily_data", "") if isinstance(market_data, dict) else ""
    h1 = market_data.get("h1_data", "") if isinstance(market_data, dict) else ""
    current_price = market_data.get("current_price", "") if isinstance(market_data, dict) else ""
    user_prompt = f"Here is the market data for {symbol}:\nCurrent Price: {current_price}\n\nDaily:\n{daily}\n\nH1:\n{h1}"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        content = data['choices'][0]['message']['content']
        parsed = json.loads(content)
        if "signal" not in parsed:
            parsed["signal"] = "HOLD"
        if "confidence_score" not in parsed:
            parsed["confidence_score"] = 50
        if "logic" not in parsed:
            parsed["logic"] = f"Market structure analyzed for {symbol}."
        return parsed
    except Exception as e:
        print(f"[DeepSeek Error for {symbol}]: {e}")
        return {"signal": "HOLD", "confidence_score": 0, "logic": f"AI decision error for {symbol}: {e}"}

