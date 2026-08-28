import platform
import config

if platform.system() != "Windows":
    # Mock execution for Mac Testing
    def execute_trade(signal):
        if signal == "HOLD":
            return "No trade placed."
        return f"MOCKED: Successfully placed {signal} order for {config.SYMBOL} with SL/TP."
else:
    import MetaTrader5 as mt5

    def execute_trade(signal):
        if signal == "HOLD":
            return "No trade placed."
            
        action = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        
        symbol_info = mt5.symbol_info_tick(config.SYMBOL)
        price = symbol_info.ask if signal == "BUY" else symbol_info.bid
        point = mt5.symbol_info(config.SYMBOL).point
        
        # Calculate SL and TP based on config points
        if signal == "BUY":
            sl = price - (config.SL_POINTS * point)
            tp = price + (config.TP_POINTS * point)
        else: # SELL
            sl = price + (config.SL_POINTS * point)
            tp = price - (config.TP_POINTS * point)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": config.SYMBOL,
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
        
        return f"Successfully placed {signal} order for {config.SYMBOL} with SL/TP!"
