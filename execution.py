# execution.py

import MetaTrader5 as mt5

import config

MAGIC_NUMBER = 123456


def _resolve_filling_mode(symbol_info):
    """Determine supported order filling mode dynamically."""
    filling_mode = int(symbol_info.filling_mode)
    if filling_mode & 2:  # SYMBOL_FILLING_IOC
        return mt5.ORDER_FILLING_IOC
    elif filling_mode & 1:  # SYMBOL_FILLING_FOK
        return mt5.ORDER_FILLING_FOK
    else:
        return mt5.ORDER_FILLING_RETURN


def get_open_positions(symbol=None):
    """
    Retrieve currently open positions from MetaTrader 5.

    If symbol is specified, matches both exact symbol (e.g. 'XAUUSDm')
    and base symbol without suffix (e.g. 'XAUUSD') to prevent duplicate orders
    regardless of broker suffix conventions.

    Returns:
        list of mt5.TradePosition objects
    """
    from data_engine import initialize_mt5
    initialize_mt5()

    if symbol:
        positions = mt5.positions_get(symbol=symbol)
        if positions is not None and len(positions) > 0:
            return list(positions)

        # Suffix-agnostic fallback: match base symbols across all open positions
        all_positions = mt5.positions_get()
        if all_positions:
            target_base = symbol.rstrip("m").upper()
            matched = [
                p for p in all_positions
                if p.symbol == symbol or p.symbol.rstrip("m").upper() == target_base
            ]
            return matched
        return []

    positions = mt5.positions_get()
    return list(positions) if positions is not None else []


def close_position(position_or_ticket):
    """
    Close an open MT5 position by ticket or TradePosition object.

    Args:
        position_or_ticket: mt5.TradePosition object or integer ticket ID.

    Returns:
        dict with details of the close execution (deal, order, price, volume, ticket, closed_side).
    """
    from data_engine import initialize_mt5
    initialize_mt5()

    if isinstance(position_or_ticket, int):
        positions = mt5.positions_get(ticket=position_or_ticket)
        if not positions:
            raise RuntimeError(f"Position #{position_or_ticket} not found on MT5.")
        position = positions[0]
    else:
        position = position_or_ticket

    symbol = str(position.symbol)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f"Could not retrieve symbol information for {symbol}")

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Could not select symbol {symbol}")

    digits = symbol_info.digits
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Could not retrieve current tick for {symbol}")

    if position.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = round(float(tick.bid), digits)
        closed_side = "BUY"
    elif position.type == mt5.POSITION_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = round(float(tick.ask), digits)
        closed_side = "SELL"
    else:
        raise ValueError(f"Unknown position type: {position.type}")

    type_filling = _resolve_filling_mode(symbol_info)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": int(position.ticket),
        "symbol": symbol,
        "volume": float(position.volume),
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"Close #{position.ticket} AI Hedge Fund",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }

    result = mt5.order_send(request)
    if result is None:
        raise RuntimeError(f"MT5 order_send() returned None: {mt5.last_error()}")

    # If filling mode rejected (10030), retry with alternate filling modes
    if result.retcode == 10030:
        for alt_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]:
            if alt_mode != type_filling:
                request["type_filling"] = alt_mode
                retry_res = mt5.order_send(request)
                if retry_res and retry_res.retcode == mt5.TRADE_RETCODE_DONE:
                    result = retry_res
                    break

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(
            f"Failed to close position #{position.ticket} for {symbol}. "
            f"Retcode: {result.retcode}, Comment: {result.comment}"
        )

    return {
        "deal": int(result.deal),
        "order": int(result.order),
        "price": float(result.price),
        "volume": float(result.volume),
        "ticket": int(position.ticket),
        "symbol": symbol,
        "closed_side": closed_side,
    }


def close_positions_for_symbol(symbol):
    """
    Close all open positions for a given symbol.

    Returns:
        list of close result dicts
    """
    positions = get_open_positions(symbol)
    results = []
    for pos in positions:
        res = close_position(pos)
        results.append(res)
    return results


def execute_trade(
    symbol,
    signal,
    stop_loss,
    take_profit,
    risk_percent,
    prevent_duplicate=True,
    close_opposite=False,
):
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

    from data_engine import initialize_mt5
    initialize_mt5()

    # ---------------------------------------------------------
    # Guard against duplicate positions / handle reversals
    # ---------------------------------------------------------

    if prevent_duplicate or close_opposite:
        existing_positions = get_open_positions(symbol)

        same_side = [
            p for p in existing_positions
            if (p.type == mt5.POSITION_TYPE_BUY and signal == "BUY")
            or (p.type == mt5.POSITION_TYPE_SELL and signal == "SELL")
        ]
        opposite_side = [
            p for p in existing_positions
            if (p.type == mt5.POSITION_TYPE_BUY and signal == "SELL")
            or (p.type == mt5.POSITION_TYPE_SELL and signal == "BUY")
        ]

        if prevent_duplicate and same_side:
            raise RuntimeError(
                f"Duplicate position rejected: {symbol} already has an active {signal} "
                f"position (ticket #{same_side[0].ticket}, volume={same_side[0].volume})."
            )

        if close_opposite and opposite_side:
            for opp_pos in opposite_side:
                close_position(opp_pos)

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
    step_str = str(symbol_info.volume_step)
    vol_digits = len(step_str.split(".")[1]) if "." in step_str else 0
    volume = round(volume, vol_digits)

    # Determine supported filling mode dynamically
    type_filling = _resolve_filling_mode(symbol_info)

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
        "magic": MAGIC_NUMBER,
        "comment": "AI Hedge Fund",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }

    # ---------------------------------------------------------
    # Send order
    # ---------------------------------------------------------

    result = mt5.order_send(request)

    if result is None:
        raise RuntimeError(
            f"MT5 order_send() returned None: {mt5.last_error()}"
        )

    # Retry with alternate filling mode if 10030 occurs
    if result.retcode == 10030:
        for alt_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]:
            if alt_mode != type_filling:
                request["type_filling"] = alt_mode
                retry_res = mt5.order_send(request)
                if retry_res and retry_res.retcode == mt5.TRADE_RETCODE_DONE:
                    result = retry_res
                    break

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
