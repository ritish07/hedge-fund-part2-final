# data_engine.py

import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta

import config


ATR_LENGTH = 14
RSI_LENGTH = 14
EMA_LENGTH = 200
RELATIVE_VOLUME_LENGTH = 20


def _add_market_indicators(dataframe):
    """Add the technical indicators used by the trading decision engine."""

    dataframe = dataframe.copy()
    dataframe["atr_14"] = ta.atr(
        high=dataframe["high"],
        low=dataframe["low"],
        close=dataframe["close"],
        length=ATR_LENGTH,
    )
    dataframe["rsi_14"] = ta.rsi(dataframe["close"], length=RSI_LENGTH)
    dataframe["ema_200"] = ta.ema(dataframe["close"], length=EMA_LENGTH)

    average_volume = ta.sma(
        dataframe["tick_volume"], length=RELATIVE_VOLUME_LENGTH
    )
    dataframe["relative_volume"] = dataframe["tick_volume"] / average_volume

    return dataframe


def _latest_market_context(dataframe):
    """Return the most recent fully calculated indicator values for the LLM."""

    latest = dataframe.iloc[-1]
    fields = (
        "close",
        "tick_volume",
        "atr_14",
        "rsi_14",
        "ema_200",
        "relative_volume",
    )
    return {
        field: round(float(latest[field]), 6)
        if pd.notna(latest[field])
        else None
        for field in fields
    }


def initialize_mt5():
    """
    Initialize connection to the running MetaTrader 5 terminal.
    """

    init_kwargs = {}
    if getattr(config, "MT5_PATH", None):
        init_kwargs["path"] = config.MT5_PATH

    if not mt5.initialize(**init_kwargs):
        error = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {error}")

    expected_login = getattr(config, "MT5_LOGIN", None)
    acc = mt5.account_info()
    if expected_login and acc and acc.login != expected_login:
        if getattr(config, "MT5_PASSWORD", None) and getattr(config, "MT5_SERVER", None):
            if not mt5.login(login=expected_login, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
                raise RuntimeError(
                    f"Failed to log into MT5 account {expected_login}: {mt5.last_error()}"
                )
        else:
            raise RuntimeError(
                f"Connected MT5 account is {acc.login}, but expected {expected_login}"
            )

    return True


def fetch_correlated_asset_prices(symbol, monitored_symbols):
    """Capture live prices for the other assets monitored by this strategy."""

    prices = {}

    for related_symbol in monitored_symbols:
        if related_symbol == symbol:
            continue

        if not mt5.symbol_select(related_symbol, True):
            prices[related_symbol] = None
            continue

        tick = mt5.symbol_info_tick(related_symbol)
        prices[related_symbol] = (
            {
                "bid": float(tick.bid),
                "ask": float(tick.ask),
                "last": float(tick.last),
            }
            if tick is not None
            else None
        )

    return prices


def fetch_multi_timeframe_data(symbol):
    """
    Fetch market data for a symbol.

    Daily:
        Last 10 candles plus indicator context -> Macro trend

    1-Hour:
        Last 24 candles plus indicator context -> Micro momentum

    Returns:
        {
            "symbol": symbol,
            "daily_csv": "...",
            "hourly_csv": "...",
            "market_context": {"daily": {...}, "h1": {...}},
            "equity": float,
            "ask": float
        }
    """

    # Make sure MT5 is initialized
    expected_login = getattr(config, "MT5_LOGIN", None)
    acc = mt5.account_info() if mt5.terminal_info() else None
    if acc is None or (expected_login and acc.login != expected_login):
        initialize_mt5()

    # Make sure the symbol is available
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Could not select symbol: {symbol}")

    # ---------------------------------------------------------
    # Fetch Daily candles - Macro Trend
    # ---------------------------------------------------------

    daily_rates = mt5.copy_rates_from_pos(
        symbol,
        mt5.TIMEFRAME_D1,
        0,
        EMA_LENGTH + 50
    )

    if daily_rates is None or len(daily_rates) == 0:
        raise RuntimeError(
            f"Failed to fetch Daily data for {symbol}: {mt5.last_error()}"
        )

    daily_df = pd.DataFrame(daily_rates)

    # Convert Unix timestamp to readable datetime
    daily_df["time"] = pd.to_datetime(
        daily_df["time"],
        unit="s"
    )

    daily_df = _add_market_indicators(daily_df)
    daily_context = _latest_market_context(daily_df)

    # Keep the LLM payload focused on recent price action.
    daily_csv = daily_df.tail(10).to_csv(index=False)

    # ---------------------------------------------------------
    # Fetch 1-Hour candles - Micro Momentum
    # ---------------------------------------------------------

    hourly_rates = mt5.copy_rates_from_pos(
        symbol,
        mt5.TIMEFRAME_H1,
        0,
        EMA_LENGTH + 50
    )

    if hourly_rates is None or len(hourly_rates) == 0:
        raise RuntimeError(
            f"Failed to fetch 1-Hour data for {symbol}: {mt5.last_error()}"
        )

    hourly_df = pd.DataFrame(hourly_rates)

    # Convert Unix timestamp to readable datetime
    hourly_df["time"] = pd.to_datetime(
        hourly_df["time"],
        unit="s"
    )

    hourly_df = _add_market_indicators(hourly_df)
    hourly_context = _latest_market_context(hourly_df)

    # Keep the LLM payload focused on recent price action.
    hourly_csv = hourly_df.tail(24).to_csv(index=False)

    # ---------------------------------------------------------
    # Current account equity
    # ---------------------------------------------------------

    account_info = mt5.account_info()

    if account_info is None:
        raise RuntimeError(
            f"Failed to retrieve account information: {mt5.last_error()}"
        )

    equity = float(account_info.equity)

    # ---------------------------------------------------------
    # Current Ask Price
    # ---------------------------------------------------------

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        raise RuntimeError(
            f"Failed to retrieve current tick for {symbol}: "
            f"{mt5.last_error()}"
        )

    ask_price = float(tick.ask)

    # ---------------------------------------------------------
    # Return everything
    # ---------------------------------------------------------

    return {
        "symbol": symbol,
        "daily_csv": daily_csv,
        "hourly_csv": hourly_csv,
        "market_context": {
            "daily": daily_context,
            "h1": hourly_context,
        },
        "equity": equity,
        "ask": ask_price
    }
