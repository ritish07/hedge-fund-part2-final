# config.py

import os
from pathlib import Path

# Load .env file if present
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip().strip('"\''))

# Trading symbols available to the AI Hedge Fund
SYMBOLS = [
    "EURUSDm",
    "GBPUSDm",
    "USDJPYm",
    "USDCHFm",
    "USDCADm",
    "AUDUSDm",
    "NZDUSDm",
    "BTCUSDm",
    "XAUUSDm",
]

# Institutional scan intervals (in seconds)
INSTITUTIONAL_INTERVALS = {
    60: "1 minute (M1)",
    300: "5 minutes (M5)",
    900: "15 minutes (M15)",
    1800: "30 minutes (M30)",
    3600: "1 hour (H1)",
    14400: "4 hours (H4)",
    86400: "1 day (D1)",
}
DEFAULT_SCAN_INTERVAL = 3600  # 1 hour standard institutional default

# Risk management
# 0.002 = 0.20%
# 0.004 = 0.40%
SL_PERCENT = 0.002
TP_PERCENT = 0.004

# DeepSeek API
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY")

# MT5 Configuration
_raw_login = os.environ.get("MT5_LOGIN", "").strip()
MT5_LOGIN = int(_raw_login) if _raw_login.isdigit() else None
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
MT5_PATH = os.environ.get("MT5_PATH", "")