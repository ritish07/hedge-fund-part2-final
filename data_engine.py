import platform
import random
import config

if platform.system() != "Windows":
    # Mock data for Mac UI testing
    def fetch_multi_timeframe_data(symbol):
        return {
            "daily_data": "Date,Open,High,Low,Close\n2024-05-01,1.050,1.060,1.045,1.055\n2024-05-02,1.055,1.065,1.050,1.062\n",
            "h1_data": "Time,Open,High,Low,Close\n10:00,1.060,1.062,1.058,1.061\n11:00,1.061,1.063,1.060,1.062\n",
            "current_price": round(random.uniform(1.050, 1.070), 4),
            "equity": round(random.uniform(9950.0, 10150.0), 2)
        }
else:
    import MetaTrader5 as mt5
    import pandas as pd

    def initialize_mt5():
        params = {}
        if hasattr(config, "MT5_PATH") and config.MT5_PATH:
            params["path"] = config.MT5_PATH
        if hasattr(config, "MT5_LOGIN") and config.MT5_LOGIN and hasattr(config, "MT5_PASSWORD") and config.MT5_PASSWORD and hasattr(config, "MT5_SERVER") and config.MT5_SERVER:
            params["login"] = int(config.MT5_LOGIN)
            params["password"] = config.MT5_PASSWORD
            params["server"] = config.MT5_SERVER

        if not mt5.initialize(**params):
            print(f"[MT5] Initialization failed: {mt5.last_error()}")
            return False
        return True

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

    def fetch_multi_timeframe_data(symbol):
        if not initialize_mt5():
            return None

        actual_symbol = resolve_symbol(symbol)

        # Fetch Daily Macro Data (Last 10 candles)
        daily_rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_D1, 0, 10)
        if daily_rates is not None and len(daily_rates) > 0:
            df_daily = pd.DataFrame(daily_rates)
            df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')
            daily_csv = df_daily[['time', 'open', 'high', 'low', 'close']].to_csv(index=False)
        else:
            daily_csv = f"No daily rates available for {actual_symbol}"

        # Fetch H1 Micro Data (Last 24 candles)
        h1_rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_H1, 0, 24)
        if h1_rates is not None and len(h1_rates) > 0:
            df_h1 = pd.DataFrame(h1_rates)
            df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
            h1_csv = df_h1[['time', 'open', 'high', 'low', 'close']].to_csv(index=False)
        else:
            h1_csv = f"No H1 rates available for {actual_symbol}"
        
        # Get Current Equity
        account_info = mt5.account_info()
        equity = account_info.equity if account_info else 0.0
        tick = mt5.symbol_info_tick(actual_symbol)
        current_price = tick.ask if tick else 0.0

        return {
            "daily_data": daily_csv,
            "h1_data": h1_csv,
            "current_price": current_price,
            "equity": equity
        }
