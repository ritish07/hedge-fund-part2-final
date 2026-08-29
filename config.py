import os
import platform

# Load local .env file if present
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# MT5 Account Credentials
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

# Ensure these match EXACTLY with your MT5 Market Watch (e.g. if your broker uses 'EURUSDm', add the 'm'!)
SYMBOLS = ["EURUSDm", "GBPUSDm", "USDJPYm", "BTCUSDm", "ETHUSDm", "XAUUSDm"]
TIMEFRAME = "H1"
TRADE_LOT_SIZE = 0.01 # Adjusted to 0.01 for micro accounts as seen in your logs

# Dynamic Stop Loss and Take Profit (Using Percentages so it works perfectly across Crypto, Gold, and Forex)
# 0.002 = 0.2% risk (Roughly 20 pips on EURUSD, $120 on BTC)
SL_PERCENT = 0.002
TP_PERCENT = 0.004

# DEEPSEEK API CONFIGURATION
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

