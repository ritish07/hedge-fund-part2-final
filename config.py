import platform

# Ensure these match EXACTLY with your MT5 Market Watch (e.g. if your broker uses 'EURUSDm', add the 'm'!)
SYMBOLS = ["EURUSDm", "GBPUSDm", "USDJPYm", "BTCUSDm", "ETHUSDm", "XAUUSDm"]
TIMEFRAME = "H1"
TRADE_LOT_SIZE = 0.01 # Adjusted to 0.01 for micro accounts as seen in your logs

# Dynamic Stop Loss and Take Profit (Using Percentages so it works perfectly across Crypto, Gold, and Forex)
# 0.002 = 0.2% risk (Roughly 20 pips on EURUSD, $120 on BTC)
SL_PERCENT = 0.002
TP_PERCENT = 0.004

# DEEPSEEK API CONFIGURATION
DEEPSEEK_API_KEY = "sk-your-deepseek-api-key-here"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
