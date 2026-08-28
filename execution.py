import platform
import config

if platform.system() != "Windows":
    # Mock execution for Mac Testing
    def execute_trade(signal):
        if signal == "HOLD":
            return "No trade placed."
        return f"MOCKED: Successfully placed {signal} order for {config.SYMBOL}."
else:
    import MetaTrader5 as mt5

    def execute_trade(signal):
        if signal == "HOLD":
            return "No trade placed."
            
        action = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(config.SYMBOL).ask if signal == "BUY" else mt5.symbol_info_tick(config.SYMBOL).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": config.SYMBOL,
            "volume": config.TRADE_LOT_SIZE,
            "type": action,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "AI Bot V2",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return f"Order failed: {result.comment}"
        
        return f"Successfully placed {signal} order for {config.SYMBOL}!"
