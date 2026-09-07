# execution.py

import MetaTrader5 as mt5

import config


def execute_trade(symbol, signal, stop_loss, take_profit, risk_percent):
    """
    Execute a BUY or SELL market order on MetaTrader 5.

    The ATR-derived stop loss and take profit are supplied by the AI decision.

    Returns:
        MT5 trade result object
    """

    # ---------------------------------------------------------
    # Validate signal
    # ---------------------------------------------------------

    signal = signal.upper()

    if signal not in ["BUY", "SELL", "HOLD"]:
        raise ValueError(
            f"Invalid trading signal: {signal}"
        )

    # HOLD = no trade
    if signal == "HOLD":
        return {
            "status": "HOLD",
            "message": "AI returned HOLD. No trade executed."
        }

    # ---------------------------------------------------------
    # Initialize MT5
    # ---------------------------------------------------------

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    # ---------------------------------------------------------
    # Get symbol information
    # ---------------------------------------------------------

    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        raise RuntimeError(
            f"Could not retrieve symbol information for {symbol}"
        )

    # Make sure symbol is visible in Market Watch
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Could not select symbol {symbol}"
            )

    # ---------------------------------------------------------
    # CRITICAL: Get symbol-specific decimal precision
    # ---------------------------------------------------------

    digits = symbol_info.digits

    # ---------------------------------------------------------
    # Get current market tick
    # ---------------------------------------------------------

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        raise RuntimeError(
            f"Could not retrieve current tick for {symbol}"
        )

    ask_price = float(tick.ask)
    bid_price = float(tick.bid)

    # ---------------------------------------------------------
    # Use AI-calculated ATR stop loss / take profit
    # ---------------------------------------------------------

    if signal == "BUY":

        price = ask_price

        order_type = mt5.ORDER_TYPE_BUY

    else:  # SELL

        price = bid_price

        order_type = mt5.ORDER_TYPE_SELL

    # ---------------------------------------------------------
    # CRITICAL:
    # Round SL and TP using the broker's symbol digits
    # ---------------------------------------------------------

    sl = round(float(stop_loss), digits)
    tp = round(float(take_profit), digits)
    price = round(price, digits)

    if signal == "BUY" and not sl < price < tp:
        raise ValueError("BUY protection levels must bracket the current price")
    if signal == "SELL" and not tp < price < sl:
        raise ValueError("SELL protection levels must bracket the current price")

    # ---------------------------------------------------------
    # Size the trade so the stop loss risks the selected share of equity.
    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError("Could not retrieve MT5 account information")

    risk_amount = float(account_info.equity) * (float(risk_percent) / 100)
    stop_distance = abs(price - sl)
    tick_size = float(symbol_info.trade_tick_size)
    tick_value = float(symbol_info.trade_tick_value)

    if stop_distance <= 0 or tick_size <= 0 or tick_value <= 0:
        raise RuntimeError("Cannot calculate risk-based volume for this symbol")

    loss_per_lot = (stop_distance / tick_size) * tick_value
    raw_volume = risk_amount / loss_per_lot
    volume_step = float(symbol_info.volume_step)
    volume = round(raw_volume / volume_step) * volume_step
    volume = max(float(symbol_info.volume_min), volume)
    volume = min(float(symbol_info.volume_max), volume)
    volume = round(volume, 8)

    # Build MT5 trade request
    # ---------------------------------------------------------

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 123456,
        "comment": "AI Hedge Fund",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # ---------------------------------------------------------
    # Send order
    # ---------------------------------------------------------

    result = mt5.order_send(request)

    if result is None:
        raise RuntimeError(
            f"MT5 order_send() returned None: {mt5.last_error()}"
        )

    # ---------------------------------------------------------
    # Check execution result
    # ---------------------------------------------------------

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(
            f"Trade execution failed for {symbol}. "
            f"Retcode: {result.retcode}, "
            f"Comment: {result.comment}"
        )

    # ---------------------------------------------------------
    # Return successful result
    # ---------------------------------------------------------

    return {
        "deal": int(result.deal),
        "order": int(result.order),
        "price": float(result.price),
        "volume": float(result.volume),
        "stop_loss": sl,
        "take_profit": tp,
    }
