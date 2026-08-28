import platform
import random
import config

if platform.system() != "Windows":
    # Mock data for Mac UI testing
    def fetch_multi_timeframe_data():
        return {
            "daily_data": "Date,Open,High,Low,Close\n2024-05-01,1.050,1.060,1.045,1.055\n2024-05-02,1.055,1.065,1.050,1.062\n",
            "h1_data": "Time,Open,High,Low,Close\n10:00,1.060,1.062,1.058,1.061\n11:00,1.061,1.063,1.060,1.062\n",
            "current_price": round(random.uniform(1.050, 1.070), 4),
            "equity": round(random.uniform(9950.0, 10150.0), 2)
        }
else:
    import MetaTrader5 as mt5
    import pandas as pd

    def fetch_multi_timeframe_data():
        if not mt5.initialize(login=config.MT5_LOGIN, server=config.MT5_SERVER, password=config.MT5_PASSWORD):
            return None

        # Fetch Daily Macro Data (Last 5 candles)
        daily_rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_D1, 0, 5)
        df_daily = pd.DataFrame(daily_rates)
        df_daily['time'] = pd.to_datetime(df_daily['time'], unit='s')
        daily_csv = df_daily[['time', 'open', 'high', 'low', 'close']].to_csv(index=False)

        # Fetch H1 Micro Data (Last 15 candles)
        h1_rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_H1, 0, 15)
        df_h1 = pd.DataFrame(h1_rates)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        h1_csv = df_h1[['time', 'open', 'high', 'low', 'close']].to_csv(index=False)
        
        # Get Current Equity
        account_info = mt5.account_info()
        equity = account_info.equity if account_info else 0.0
        current_price = mt5.symbol_info_tick(config.SYMBOL).ask

        return {
            "daily_data": daily_csv,
            "h1_data": h1_csv,
            "current_price": current_price,
            "equity": equity
        }
