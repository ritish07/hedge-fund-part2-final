# main.py

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import MetaTrader5 as mt5
from data_engine import (
    fetch_correlated_asset_prices,
    fetch_multi_timeframe_data,
    initialize_mt5,
)
from ai_brain import get_ai_decision
from auditor import load_rules_document, run_audit
from execution import close_position, execute_trade, get_open_positions
from memory_store import append_trade_memory, reconcile_closed_trades
from macro_engine import get_macro_context, refresh_macro_context


app = FastAPI(
    title="Autonomous AI Hedge Fund",
    description="AI-powered automated MT5 trading system",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ============================================================
# GLOBAL BOT STATE
# ============================================================

bot_state = {
    "is_running": True,
    "interval": getattr(config, "DEFAULT_SCAN_INTERVAL", 3600),
    "risk_percent": 1.0,
    "equity": 0.0,
    "last_logic": "",
    "last_confidence": 0,
    "last_signal": "HOLD",
    "last_entry_price": None,
    "last_stop_loss": None,
    "last_take_profit": None,
    "trade_history": [],
    "open_positions": [],
    "learned_rules": [],
    "last_audit_at": None,
    "macro_state": None,
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

        if request.interval < 60:
            return {
                "status": "error",
                "message": "interval must be at least 60 seconds (institutional timeframe minimum)"
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
# POSITION FORMATTER & CLOSE ENDPOINT
# ============================================================

def format_position(pos):
    return {
        "ticket": int(pos.ticket),
        "symbol": str(pos.symbol),
        "side": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
        "volume": float(pos.volume),
        "open_price": float(pos.price_open),
        "sl": float(pos.sl),
        "tp": float(pos.tp),
        "current_price": float(pos.price_current),
        "profit": float(pos.profit),
        "time": int(pos.time),
    }


class CloseRequest(BaseModel):
    ticket: int


@app.post("/api/close")
async def close_position_endpoint(request: CloseRequest):
    try:
        res = await asyncio.to_thread(close_position, request.ticket)
        acc = mt5.account_info()
        if acc:
            bot_state["equity"] = float(acc.equity)
        positions = await asyncio.to_thread(get_open_positions)
        bot_state["open_positions"] = [format_position(p) for p in positions]
        return {"status": "success", "result": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# AUDIT & RULES ENDPOINTS
# ============================================================

class AuditRequest(BaseModel):
    force: bool = True


@app.post("/api/audit")
async def trigger_audit(request: AuditRequest = None):
    force = request.force if request else True
    res = await asyncio.to_thread(run_audit, force)
    rules_doc = await asyncio.to_thread(load_rules_document)
    bot_state["learned_rules"] = rules_doc.get("rules", [])
    bot_state["last_audit_at"] = rules_doc.get("last_audit_at")
    return {"status": "success", "audit": res, "rules": rules_doc.get("rules", [])}


@app.get("/api/rules")
async def get_rules():
    rules_doc = await asyncio.to_thread(load_rules_document)
    return rules_doc


# ============================================================
# MACRO & GEOPOLITICAL INTELLIGENCE ENDPOINTS
# ============================================================

@app.get("/api/macro")
async def get_macro_endpoint():
    macro = await asyncio.to_thread(get_macro_context)
    bot_state["macro_state"] = macro
    return macro


@app.post("/api/macro/refresh")
async def refresh_macro_endpoint():
    macro = await asyncio.to_thread(refresh_macro_context)
    bot_state["macro_state"] = macro
    return {"status": "success", "macro_state": macro}


# ============================================================
# STATUS ENDPOINT
# ============================================================

@app.get("/api/status")
async def get_status():
    try:
        positions = get_open_positions()
        bot_state["open_positions"] = [format_position(p) for p in positions]
        acc = mt5.account_info()
        if acc:
            bot_state["equity"] = float(acc.equity)
        rules_doc = load_rules_document()
        bot_state["learned_rules"] = rules_doc.get("rules", [])
        bot_state["last_audit_at"] = rules_doc.get("last_audit_at")
        bot_state["macro_state"] = get_macro_context()
    except Exception:
        pass
    return bot_state


# ============================================================
# TRADING LOOP
# ============================================================

async def trading_loop():

    while True:

        # ----------------------------------------------------
        # Only trade when bot is running
        # ----------------------------------------------------

        if not bot_state["is_running"]:
            await asyncio.sleep(1)
            continue

        print("[SYSTEM] Starting market analysis cycle across symbols...", flush=True)

        for symbol in config.SYMBOLS:

            # Bot may have been stopped while processing
            if not bot_state["is_running"]:
                break

            try:

                # ------------------------------------------------
                # 1. Fetch market data
                # ------------------------------------------------

                market_data = await asyncio.to_thread(
                    fetch_multi_timeframe_data, symbol
                )

                # Update current account equity
                bot_state["equity"] = market_data["equity"]

                # ------------------------------------------------
                # 2. Ask AI for decision
                # ------------------------------------------------

                decision = await asyncio.to_thread(
                    get_ai_decision, market_data, symbol
                )

                signal = decision["signal"]
                confidence = decision["confidence_score"]
                logic = decision["logic"]
                stop_loss = decision["stop_loss"]
                take_profit = decision["take_profit"]

                # Store latest AI analysis
                bot_state["last_logic"] = f"[{symbol}] {logic}"
                bot_state["last_confidence"] = confidence
                bot_state["last_signal"] = signal
                bot_state["last_entry_price"] = market_data["ask"]
                bot_state["last_stop_loss"] = stop_loss
                bot_state["last_take_profit"] = take_profit

                print(
                    f"[AI] {symbol} | "
                    f"Signal={signal} | "
                    f"Confidence={confidence} | "
                    f"Logic={logic}",
                    flush=True
                )

                # ------------------------------------------------
                # 3. Execute BUY / SELL (with duplicate and reversal guards)
                # ------------------------------------------------

                if signal in ["BUY", "SELL"]:

                    # Check for existing open positions for this symbol
                    open_positions = await asyncio.to_thread(get_open_positions, symbol)

                    same_side_positions = [
                        p for p in open_positions
                        if (p.type == mt5.POSITION_TYPE_BUY and signal == "BUY")
                        or (p.type == mt5.POSITION_TYPE_SELL and signal == "SELL")
                    ]
                    opposite_positions = [
                        p for p in open_positions
                        if (p.type == mt5.POSITION_TYPE_BUY and signal == "SELL")
                        or (p.type == mt5.POSITION_TYPE_SELL and signal == "BUY")
                    ]

                    # 1. DUPLICATE CHECK: Do NOT open duplicate positions in the same direction
                    if same_side_positions:
                        existing_ticket = same_side_positions[0].ticket
                        print(
                            f"[DUPLICATE PREVENTED] {symbol} | Active {signal} position already exists "
                            f"(Ticket #{existing_ticket}, Vol={same_side_positions[0].volume}). Skipping new trade.",
                            flush=True,
                        )
                        bot_state["last_logic"] = (
                            f"[{symbol}] Holding active {signal} position (#{existing_ticket}). {logic}"
                        )
                        # Clean up any stale opposite positions if present
                        for opp_pos in opposite_positions:
                            opp_side = "BUY" if opp_pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            print(
                                f"[CLEANUP] {symbol} | Closing conflicting {opp_side} #{opp_pos.ticket}...",
                                flush=True,
                            )
                            await asyncio.to_thread(close_position, opp_pos)
                        continue

                    # 2. REVERSAL CHECK: If AI decision changed direction, close previous position first
                    if opposite_positions:
                        closed_all = True
                        for opp_pos in opposite_positions:
                            opp_side = "BUY" if opp_pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            print(
                                f"[REVERSAL] {symbol} | AI decision reversed from {opp_side} to {signal}. "
                                f"Closing previous {opp_side} position #{opp_pos.ticket} before opening new {signal}...",
                                flush=True,
                            )
                            try:
                                close_res = await asyncio.to_thread(close_position, opp_pos)
                                print(
                                    f"[CLOSE] {symbol} | Closed {opp_side} #{opp_pos.ticket} "
                                    f"(Deal #{close_res['deal']}) at {close_res['price']}",
                                    flush=True,
                                )
                                close_record = {
                                    "time": datetime.now(timezone.utc).isoformat(),
                                    "asset": opp_pos.symbol,
                                    "signal": f"CLOSE {opp_side}",
                                    "logic": f"Reversal: Closed {opp_side} to open {signal} (AI: {logic})",
                                    "entry_price": close_res["price"],
                                    "stop_loss": 0.0,
                                    "take_profit": 0.0,
                                    "volume": close_res["volume"],
                                    "risk_percent": bot_state["risk_percent"],
                                    "deal": close_res["deal"],
                                    "order": close_res["order"],
                                    "status": "CLOSED",
                                }
                                bot_state["trade_history"].append(close_record)
                            except Exception as close_err:
                                print(
                                    f"[ERROR] {symbol} | Failed to close previous {opp_side} position #{opp_pos.ticket}: {close_err}",
                                    flush=True,
                                )
                                closed_all = False
                                break

                        if not closed_all:
                            print(
                                f"[WARNING] {symbol} | Aborting new {signal} trade because previous position could not be closed.",
                                flush=True,
                            )
                            continue

                    # 3. Open new trade
                    result = await asyncio.to_thread(
                        execute_trade,
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
                        "time": datetime.now(timezone.utc).isoformat(),
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

                    # Correlated asset prices
                    correlated_prices = await asyncio.to_thread(
                        fetch_correlated_asset_prices,
                        symbol,
                        config.SYMBOLS,
                    )

                    memory_record = {
                        **trade_info,
                        "market_context": {
                            "captured_at": trade_info["time"],
                            "volume": {
                                "h1_tick_volume": market_data["market_context"]["h1"]["tick_volume"],
                                "h1_relative_volume": market_data["market_context"]["h1"]["relative_volume"],
                                "daily_tick_volume": market_data["market_context"]["daily"]["tick_volume"],
                                "daily_relative_volume": market_data["market_context"]["daily"]["relative_volume"],
                            },
                            "volatility": {
                                "h1_atr_14": market_data["market_context"]["h1"]["atr_14"],
                                "daily_atr_14": market_data["market_context"]["daily"]["atr_14"],
                            },
                            "correlated_asset_prices": correlated_prices,
                        },
                    }

                    await asyncio.to_thread(append_trade_memory, memory_record)

                    bot_state["trade_history"].append(trade_info)

                    # Update live equity and positions after trade
                    acc_info = mt5.account_info()
                    if acc_info:
                        bot_state["equity"] = float(acc_info.equity)

                    active_positions = await asyncio.to_thread(get_open_positions)
                    bot_state["open_positions"] = [format_position(p) for p in active_positions]

                    print(
                        f"[TRADE] {symbol} | {signal} | "
                        f"Deal #{result['deal']} filled at {result['price']} | "
                        f"SL={result['stop_loss']} TP={result['take_profit']} Vol={result['volume']}",
                        flush=True
                    )

                else:
                    open_positions = await asyncio.to_thread(get_open_positions, symbol)
                    if open_positions:
                        pos_summary = ", ".join(
                            f"{'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL'} #{p.ticket}"
                            for p in open_positions
                        )
                        print(
                            f"[AI] {symbol} | HOLD - Active position maintained: {pos_summary}",
                            flush=True,
                        )
                    else:
                        print(
                            f"[AI] {symbol} | HOLD - No trade",
                            flush=True,
                        )

            except Exception as e:
                print(
                    f"[ERROR] {symbol}: {str(e)}",
                    flush=True
                )

            # Small yield between symbol evaluations
            await asyncio.sleep(0.5)

        # ----------------------------------------------------
        # 4. Self-Learning: Reconcile closed trades & run audit
        # ----------------------------------------------------
        try:
            reconciled_count = await asyncio.to_thread(reconcile_closed_trades)
            if reconciled_count > 0:
                print(
                    f"[LEARNING] Reconciled {reconciled_count} closed trades from MT5. Running auditor...",
                    flush=True
                )
                audit_res = await asyncio.to_thread(run_audit, True)
                rules_doc = await asyncio.to_thread(load_rules_document)
                bot_state["learned_rules"] = rules_doc.get("rules", [])
                bot_state["last_audit_at"] = rules_doc.get("last_audit_at")
                print(
                    f"[LEARNING] Auditor finished: {audit_res.get('status')} | Active rules: {len(bot_state['learned_rules'])}",
                    flush=True
                )
        except Exception as learn_err:
            print(f"[LEARNING] Error during trade reconciliation / audit: {learn_err}", flush=True)

        # ----------------------------------------------------
        # Wait before the next complete scan
        # ----------------------------------------------------

        wait_seconds = max(1, int(bot_state["interval"]))
        print(f"[SYSTEM] Cycle complete. Next scan in {wait_seconds}s...", flush=True)
        for _ in range(wait_seconds):
            if not bot_state["is_running"]:
                break
            await asyncio.sleep(1)


# ============================================================
# DEDICATED 24-HOUR / DAILY AUTONOMOUS AUDITOR LOOP
# ============================================================

async def scheduled_daily_auditor_loop():
    """
    Dedicated autonomous auditor task running 24/7 in the background.
    Every 30 minutes, it checks whether a new UTC day has arrived or 24 hours have
    elapsed since the last audit. It automatically reconciles any closed deals from MT5,
    invokes DeepSeek to analyze losses, updates new_rules.json, and refreshes bot_state.
    """
    while True:
        try:
            # 1. Reconcile any closed trades from MT5
            reconciled = await asyncio.to_thread(reconcile_closed_trades)
            if reconciled > 0:
                print(f"[AUDITOR 24H] Reconciled {reconciled} closed trade(s) from deal history.", flush=True)

            # 2. Check if daily audit is due (run_audit checks if today UTC has already been audited)
            audit_res = await asyncio.to_thread(run_audit, False)
            if audit_res.get("status") == "success":
                rules_doc = await asyncio.to_thread(load_rules_document)
                bot_state["learned_rules"] = rules_doc.get("rules", [])
                bot_state["last_audit_at"] = rules_doc.get("last_audit_at")
                print(
                    f"[AUDITOR 24H] Daily audit completed! Active learned rules: {len(bot_state['learned_rules'])}",
                    flush=True
                )
        except Exception as e:
            print(f"[AUDITOR 24H] Periodic audit check error: {e}", flush=True)

        # Check every 30 minutes
        await asyncio.sleep(1800)


# ============================================================
# DEDICATED 15-MINUTE AUTONOMOUS MACRO & GEOPOLITICAL LOOP
# ============================================================

async def scheduled_macro_update_loop():
    """
    Dedicated background task refreshing global macro benchmarks,
    breaking news, and DeepSeek geopolitical intelligence every 15 minutes.
    """
    await asyncio.sleep(5)
    while True:
        try:
            macro = await asyncio.to_thread(refresh_macro_context)
            bot_state["macro_state"] = macro
            print(
                f"[MACRO 15M] Global Intelligence updated: Regime={macro.get('market_regime')} | "
                f"Threat={macro.get('geopolitical_risk_level')} | Gold={macro.get('gold_bias')} | BTC={macro.get('bitcoin_bias')}",
                flush=True
            )
        except Exception as e:
            print(f"[MACRO 15M] Periodic macro refresh error: {e}", flush=True)

        await asyncio.sleep(900)


# ============================================================
# START BACKGROUND TASKS
# ============================================================

@app.on_event("startup")
async def startup_event():
    try:
        initialize_mt5()
        acc = mt5.account_info()
        if acc:
            bot_state["equity"] = float(acc.equity)
            print(
                f"[SYSTEM] MT5 Connected: Account {acc.login} ({acc.server}) | Equity: ${acc.equity:,.2f}"
            )
        # Reconcile any closed trades from history on launch
        reconciled = await asyncio.to_thread(reconcile_closed_trades)
        if reconciled > 0:
            print(f"[LEARNING] Startup: Reconciled {reconciled} closed trades.")
        # Load learned rules and run audit if eligible
        audit_res = await asyncio.to_thread(run_audit, False)
        rules_doc = await asyncio.to_thread(load_rules_document)
        bot_state["learned_rules"] = rules_doc.get("rules", [])
        bot_state["last_audit_at"] = rules_doc.get("last_audit_at")
        print(
            f"[LEARNING] Startup: Auditor status: {audit_res.get('status')} | Active rules: {len(bot_state['learned_rules'])}"
        )
        # Load initial macro intelligence state
        macro = await asyncio.to_thread(get_macro_context)
        bot_state["macro_state"] = macro
        print(
            f"[MACRO] Startup: Regime={macro.get('market_regime')} | Threat={macro.get('geopolitical_risk_level')} | Gold={macro.get('gold_bias')}"
        )
    except Exception as e:
        print(f"[SYSTEM] Startup initialization warning: {e}")

    # Launch trading loop
    asyncio.create_task(
        trading_loop()
    )

    # Launch dedicated 24-hour autonomous auditor loop
    asyncio.create_task(
        scheduled_daily_auditor_loop()
    )

    # Launch dedicated 15-minute global macro & geopolitical loop
    asyncio.create_task(
        scheduled_macro_update_loop()
    )

    print(
        "[SYSTEM] Autonomous AI Hedge Fund, Global Macro Desk & 24/7 Auditor started."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
