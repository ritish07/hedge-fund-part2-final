import platform
import config

if platform.system() != "Windows":
    def execute_trade(symbol, signal):
        if signal == "HOLD":
            return "No trade placed."
        return f"MOCKED: Successfully placed {signal} order for {symbol} with SL/TP."
else:
    import MetaTrader5 as mt5

    def execute_trade(symbol, signal):
        if signal == "HOLD":
            return "No trade placed."
            
        action = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        
        symbol_info = mt5.symbol_info_tick(symbol)
        if not symbol_info:
            return f"Error: Could not retrieve ticks for {symbol}. Check if symbol is in Market Watch."
            
        price = symbol_info.ask if signal == "BUY" else symbol_info.bid
        
        # Get the correct decimal places for the symbol to prevent "Invalid Stops" format errors
        digits = mt5.symbol_info(symbol).digits
        
        # Dynamic Percentage-based SL/TP 
        if signal == "BUY":
            sl = round(price * (1 - config.SL_PERCENT), digits)
            tp = round(price * (1 + config.TP_PERCENT), digits)
        else: # SELL
            sl = round(price * (1 + config.SL_PERCENT), digits)
            tp = round(price * (1 - config.TP_PERCENT), digits)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
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
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return f"Order failed: {result.comment}"
        
        return f"Successfully placed {signal} order for {symbol} with SL/TP!"
