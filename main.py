# main.py

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

import config
from data_engine import (
    fetch_correlated_asset_prices,
    fetch_multi_timeframe_data,
)
from ai_brain import get_ai_decision
from execution import execute_trade
from memory_store import append_trade_memory


app = FastAPI(
    title="Autonomous AI Hedge Fund",
    description="AI-powered automated MT5 trading system",
    version="1.0.0"
)


# ============================================================
# GLOBAL BOT STATE
# ============================================================

bot_state = {
    "is_running": False,
    "interval": 30,
    "risk_percent": 1.0,
    "equity": 0.0,
    "last_logic": "",
    "last_confidence": 0,
    "last_signal": "HOLD",
    "last_entry_price": None,
    "last_stop_loss": None,
    "last_take_profit": None,
    "trade_history": []
}


# ============================================================
# API REQUEST MODEL
# ============================================================

class ControlRequest(BaseModel):
    action: str | None = None
    interval: int | None = None
    risk_percent: float | None = None


# ============================================================
# CONTROL ENDPOINT
# ============================================================

@app.post("/api/control")
async def control_bot(request: ControlRequest):

    # --------------------------------------------------------
    # Start / Stop
    # --------------------------------------------------------

    if request.action is not None:

        action = request.action.lower()

        if action == "start":
            bot_state["is_running"] = True

        elif action == "stop":
            bot_state["is_running"] = False

        else:
            return {
                "status": "error",
                "message": "action must be 'start' or 'stop'"
            }

    # --------------------------------------------------------
    # Update interval
    # --------------------------------------------------------

    if request.interval is not None:

        if request.interval < 1:
            return {
                "status": "error",
                "message": "interval must be at least 1 second"
            }

        bot_state["interval"] = request.interval

    if request.risk_percent is not None:
        if not 0 < request.risk_percent <= 100:
            return {
                "status": "error",
                "message": "risk_percent must be greater than 0 and no more than 100"
            }

        bot_state["risk_percent"] = request.risk_percent

    return {
        "status": "success",
        "bot_state": bot_state
    }


# ============================================================
# STATUS ENDPOINT
# ============================================================

@app.get("/api/status")
async def get_status():
    return bot_state


# ============================================================
# TRADING LOOP
# ============================================================

async def trading_loop():

    while True:

        # ----------------------------------------------------
        # Only trade when bot is running
        # ----------------------------------------------------

        if bot_state["is_running"]:

            for symbol in config.SYMBOLS:

                # Bot may have been stopped while processing
                if not bot_state["is_running"]:
                    break

                try:

                    # ------------------------------------------------
                    # 1. Fetch market data
                    # ------------------------------------------------

                    market_data = fetch_multi_timeframe_data(symbol)

                    # Update current account equity
                    bot_state["equity"] = market_data["equity"]

                    # ------------------------------------------------
                    # 2. Ask AI for decision
                    # ------------------------------------------------

                    decision = get_ai_decision(
                        market_data,
                        symbol
                    )

                    signal = decision["signal"]
                    confidence = decision["confidence_score"]
                    logic = decision["logic"]
                    stop_loss = decision["stop_loss"]
                    take_profit = decision["take_profit"]

                    # Store latest AI analysis
                    bot_state["last_logic"] = logic
                    bot_state["last_confidence"] = confidence
                    bot_state["last_signal"] = signal
                    bot_state["last_entry_price"] = market_data["ask"]
                    bot_state["last_stop_loss"] = stop_loss
                    bot_state["last_take_profit"] = take_profit

                    print(
                        f"[AI] {symbol} | "
                        f"Signal={signal} | "
                        f"Confidence={confidence}"
                    )

                    # ------------------------------------------------
                    # 3. Execute BUY / SELL
                    # ------------------------------------------------

                    if signal in ["BUY", "SELL"]:

                        result = execute_trade(
                            symbol,
                            signal,
                            stop_loss,
                            take_profit,
                            bot_state["risk_percent"],
                        )

                        # ------------------------------------------------
                        # 4. Record executed trade
                        # ------------------------------------------------

                        trade_info = {
                            "time": datetime.now(
                                timezone.utc
                            ).isoformat(),

                            "asset": symbol,

                            "signal": signal,
                            "logic": logic,
                            "entry_price": result["price"],
                            "stop_loss": result["stop_loss"],
                            "take_profit": result["take_profit"],
                            "volume": result["volume"],
                            "risk_percent": bot_state["risk_percent"],
                            "deal": result["deal"],
                            "order": result["order"],
                            "status": "CONFIRMED",
                        }

                        # Persist the exact decision context alongside the
                        # broker-confirmed fill for later learning/review.
                        memory_record = {
                            **trade_info,
                            "market_context": {
                                "captured_at": trade_info["time"],
                                "volume": {
                                    "h1_tick_volume": market_data[
                                        "market_context"
                                    ]["h1"]["tick_volume"],
                                    "h1_relative_volume": market_data[
                                        "market_context"
                                    ]["h1"]["relative_volume"],
                                    "daily_tick_volume": market_data[
                                        "market_context"
                                    ]["daily"]["tick_volume"],
                                    "daily_relative_volume": market_data[
                                        "market_context"
                                    ]["daily"]["relative_volume"],
                                },
                                "volatility": {
                                    "h1_atr_14": market_data[
                                        "market_context"
                                    ]["h1"]["atr_14"],
                                    "daily_atr_14": market_data[
                                        "market_context"
                                    ]["daily"]["atr_14"],
                                },
                                "correlated_asset_prices": (
                                    fetch_correlated_asset_prices(
                                        symbol,
                                        config.SYMBOLS,
                                    )
                                ),
                            },
                        }

                        append_trade_memory(memory_record)

                        bot_state["trade_history"].append(
                            trade_info
                        )

                        print(
                            f"[TRADE] {symbol} | "
                            f"{signal} | "
                            f"Trade executed successfully"
                        )

                    else:

                        print(
                            f"[AI] {symbol} | "
                            f"HOLD - No trade"
                        )

                except Exception as e:

                    # Don't allow one failed symbol to stop
                    # the entire hedge fund loop.

                    print(
                        f"[ERROR] {symbol}: {str(e)}"
                    )

                # Small yield so other FastAPI tasks can run
                await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # Wait before the next complete scan
        # ----------------------------------------------------

        await asyncio.sleep(
            bot_state["interval"]
        )


# ============================================================
# START BACKGROUND TRADING TASK
# ============================================================

@app.on_event("startup")
async def startup_event():

    asyncio.create_task(
        trading_loop()
    )

    print(
        "[SYSTEM] Autonomous AI Hedge Fund started."
    )
