import platform
import config

if platform.system() != "Windows":
    def execute_trade(symbol, signal):
        if signal == "HOLD":
            return "No trade placed."
        return f"MOCKED: Successfully placed {signal} order for {symbol} with SL/TP."
else:
    import MetaTrader5 as mt5

    def resolve_symbol(symbol):
        matches = mt5.symbols_get()
        if matches:
            requested = symbol.casefold()
            for item in matches:
                if item.name.casefold() == requested:
                    if not item.visible:
                        mt5.symbol_select(item.name, True)
                    return item.name
            for item in matches:
                if item.name.casefold().startswith(requested):
                    if not item.visible:
                        mt5.symbol_select(item.name, True)
                    return item.name
        return symbol

    def execute_trade(symbol, signal):
        if signal == "HOLD":
            return "No trade placed."
            
        actual_symbol = resolve_symbol(symbol)
        symbol_info = mt5.symbol_info_tick(actual_symbol)
        sym_detail = mt5.symbol_info(actual_symbol)

        if symbol_info is None or sym_detail is None:
            return f"Order failed: Symbol info for {actual_symbol} not available."

        action = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        price = symbol_info.ask if signal == "BUY" else symbol_info.bid
        point = sym_detail.point
        digits = sym_detail.digits
        
        # Dynamic Percentage-based SL/TP with broker minimum stop distance safeguards
        min_stop_dist = max((getattr(sym_detail, "stops_level", 0) + getattr(sym_detail, "spread", 0)) * point, 0.0)
        sl_dist = max(price * config.SL_PERCENT, min_stop_dist)
        tp_dist = max(price * config.TP_PERCENT, min_stop_dist * 2)
        
        if signal == "BUY":
            sl = round(price - sl_dist, digits)
            tp = round(price + tp_dist, digits)
        else: # SELL
            sl = round(price + sl_dist, digits)
            tp = round(price - tp_dist, digits)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": actual_symbol,
            "volume": config.TRADE_LOT_SIZE,
            "type": action,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": "AI Bot V2",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None:
            return f"Order failed: {mt5.last_error()}"

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return f"Order failed: {result.comment}"
        
        return f"Successfully placed {signal} order for {actual_symbol} with SL/TP!"

