"""Durable append-only memory for broker-confirmed trade executions."""

import json
from pathlib import Path


MEMORY_FILE = Path(__file__).with_name("memory.json")


def append_trade_memory(record):
    """Append a JSON-serializable confirmed-trade record to disk atomically."""

    if MEMORY_FILE.exists():
        with MEMORY_FILE.open("r", encoding="utf-8") as memory_file:
            history = json.load(memory_file)
        if not isinstance(history, list):
            raise ValueError("memory.json must contain a JSON array")
    else:
        history = []

    history.append(record)
    temporary_file = MEMORY_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as memory_file:
        json.dump(history, memory_file, indent=2)
        memory_file.write("\n")

    temporary_file.replace(MEMORY_FILE)


def reconcile_closed_trades():
    """
    Reconcile open records in memory.json against MetaTrader 5 deal history.
    Finds exit deals, records realized P/L, exit price, and outcome (WIN/LOSS/BREAKEVEN).

    Returns:
        int: Number of newly reconciled trades.
    """
    import MetaTrader5 as mt5
    from datetime import datetime, timezone
    from data_engine import initialize_mt5

    if not MEMORY_FILE.exists():
        return 0

    try:
        initialize_mt5()
    except Exception:
        return 0

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as memory_file:
            history = json.load(memory_file)
        if not isinstance(history, list):
            return 0
    except Exception:
        return 0

    modified = False
    newly_reconciled = 0

    for trade in history:
        # If already reconciled as closed with realized P/L, skip
        if trade.get("status") == "CLOSED" and trade.get("realized_pnl") is not None:
            continue

        order_id = trade.get("order")
        deal_id = trade.get("deal")

        deals = None
        if order_id:
            deals = mt5.history_deals_get(position=order_id)
        if not deals and deal_id:
            deals = mt5.history_deals_get(position=deal_id)

        if not deals:
            continue

        # Look for the closing deal (entry == mt5.DEAL_ENTRY_OUT which equals 1)
        exit_deals = [d for d in deals if getattr(d, "entry", 0) == 1]
        if exit_deals:
            exit_deal = exit_deals[0]
            trade["status"] = "CLOSED"
            trade["realized_pnl"] = round(float(exit_deal.profit), 2)
            trade["exit_price"] = round(float(exit_deal.price), 5)
            trade["exit_deal"] = int(exit_deal.ticket)
            try:
                trade["exit_time"] = datetime.fromtimestamp(exit_deal.time, tz=timezone.utc).isoformat()
            except Exception:
                pass
            trade["outcome"] = "LOSS" if exit_deal.profit < 0 else ("WIN" if exit_deal.profit > 0 else "BREAKEVEN")
            modified = True
            newly_reconciled += 1

    if modified:
        temporary_file = MEMORY_FILE.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as memory_file:
            json.dump(history, memory_file, indent=2)
            memory_file.write("\n")
        temporary_file.replace(MEMORY_FILE)

    return newly_reconciled
