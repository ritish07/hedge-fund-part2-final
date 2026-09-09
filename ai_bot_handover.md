# Hedge Fund Distributed Architecture: Linux Handover

You are an advanced AI agent running on a powerful Ubuntu/Linux server (32GB RAM, 8 Cores).
Your task is to build and run the "Quant Brain" of a highly sophisticated, distributed AI Hedge Fund.

## 1. Architectural Overview
This system operates on a **Master-Worker (Distributed) Architecture**:
1.  **Windows Execution Node (`http://<WINDOWS_IP>:8001`)**: This node runs MetaTrader5 and exposes a lightweight FastAPI gateway. It handles ONLY data fetching and trade execution.
2.  **Linux Brain Node (Your Server)**: You will run everything else. You host the Macro Intelligence engine, the LLM DeepSeek Brain, the Autonomous Auditor, and a new Machine Learning engine (XGBoost + Amazon Chronos PyTorch models).

## 2. Your Task
You need to re-implement the Hedge Fund's control loop (`main.py`), logic (`ai_brain.py`), and data aggregation (`macro_engine.py`, `data_engine.py`) on this Linux server.

### Constraints & Instructions:
*   **DO NOT IMPORT `MetaTrader5`**. You are on Linux; it will crash.
*   Whenever you need OHLCV data, you must perform an HTTP GET request to the Windows Gateway:
    `GET http://<WINDOWS_IP>:8001/api/rates/{symbol}?timeframe=H1&num_bars=2000`
    *Returns: A list of dicts: `[{"time": 171..., "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, ...}]`*
*   Whenever you need to place a trade, you must perform an HTTP POST request:
    `POST http://<WINDOWS_IP>:8001/api/execute`
    *Payload:* `{"symbol": "XAUUSDm", "action": "BUY", "volume": 0.01, "sl": 2300.0, "tp": 2400.0}`
*   Whenever you need to check positions:
    `GET http://<WINDOWS_IP>:8001/api/positions`

## 3. The Tri-Pillar ML Strategy
Because you are running on a 32GB server, you must implement the **Tri-Pillar Ensemble**:
1.  **Macro Intelligence (`macro_engine.py`)**: Real-time scraper of 10Y yields, WTI Crude Oil, DXY, and geopolitical news, feeding a prompt to DeepSeek for structural macro bias.
2.  **Quantitative ML (`quant_engine.py`)**: 
    *   Build a robust feature engineering pipeline (EMA distances, RSI, MACD, ATR bounds, lag returns).
    *   Train an XGBoost Classifier on 10,000 bars of historical data to output a hard probability score (e.g., `P(UP) = 0.72`).
    *   *Optional:* Install `amazon/chronos-bolt-mini` or `chronos-t5-mini` (PyTorch) for zero-shot probabilistic trajectory forecasting.
3.  **The LLM Gatekeeper (`ai_brain.py`)**: Send the ML Probability Score, the Technical Indicators, and the Macro Intelligence Bias to DeepSeek. DeepSeek acts as the final Risk Officer and decides to `BUY`, `SELL`, or `HOLD`.

## 4. Setup Instructions
1.  Create `.env` containing `DEEPSEEK_API_KEY` and `WINDOWS_GATEWAY_URL=http://<IP>:8001`.
2.  Install dependencies: `pip install fastapi uvicorn pandas pandas-ta xgboost scikit-learn requests jinja2 openai` (add `torch transformers` if deploying Chronos).
3.  Rewrite `data_engine.py` to calculate technical indicators locally using `pandas-ta` on the JSON data received from the Windows Gateway.
4.  Recreate the Glassmorphic HTML Dashboard (with interval scanning set to 3600 seconds) and serve it from Linux so the user can access the trading terminal via `http://<LINUX_IP>:8000`.

Start building the Linux components!
