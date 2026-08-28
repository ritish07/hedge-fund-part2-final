import requests
import json
import config

def get_ai_decision(market_data, symbol):
    if not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY == "sk-your-deepseek-api-key-here":
        # Mock Response for Mac Testing if no API key is provided
        return {
            "signal": "BUY",
            "confidence_score": 85,
            "logic": f"[{symbol}] The Daily trend is bullish, and 1H structure just broke above a major resistance level. Momentum is strong."
        }
    
    url = "https://api.deepseek.com/chat/completions"
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

    user_prompt = f"Here is the market data for {symbol}:\nDaily:\n{market_data['daily_data']}\n\nH1:\n{market_data['h1_data']}"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    try:
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        return {"signal": "ERROR", "confidence_score": 0, "logic": str(e)}
