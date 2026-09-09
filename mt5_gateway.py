import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import MetaTrader5 as mt5
import pandas as pd
import config
from execution import execute_trade, close_position, get_open_positions

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MT5 Windows Gateway", description="Execution & Data API for Linux Quant Brain")

class TradeRequest(BaseModel):
    symbol: str
    action: str  # BUY or SELL
    volume: float
    sl: float
    tp: float

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing MetaTrader5 Gateway...")
    if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER, path=config.MT5_PATH):
        logger.error(f"MT5 init failed: {mt5.last_error()}")
    else:
        logger.info("MT5 successfully initialized on Windows Gateway.")

@app.get("/api/account")
async def get_account():
    acc = mt5.account_info()
    if acc is None:
        raise HTTPException(status_code=500, detail="Failed to get account info")
    return acc._asdict()

@app.get("/api/positions")
async def get_positions():
    positions = get_open_positions()
    return [{"ticket": p.ticket, "symbol": p.symbol, "side": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL", 
             "volume": p.volume, "open_price": p.price_open, "sl": p.sl, "tp": p.tp, 
             "current_price": p.price_current, "profit": p.profit, "time": p.time} for p in positions]

@app.get("/api/rates/{symbol}")
async def get_rates(symbol: str, timeframe: str = "H1", num_bars: int = 1000):
    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, 
              "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
    if timeframe not in tf_map:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, num_bars)
    if rates is None or len(rates) == 0:
        raise HTTPException(status_code=404, detail="Failed to fetch rates")
    
    df = pd.DataFrame(rates)
    # Convert types for JSON serialization
    df['time'] = df['time'].astype(int)
    return df.to_dict(orient="records")

@app.post("/api/execute")
async def execute(req: TradeRequest):
    # Pass exactly to our existing robust execution.py function
    res = execute_trade(req.symbol, req.action, req.volume, req.sl, req.tp)
    if not res:
        raise HTTPException(status_code=500, detail="Trade execution failed")
    return {"status": "success", "ticket": res.order}

@app.post("/api/close/{ticket}")
async def close(ticket: int):
    success = close_position(ticket)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to close ticket")
    return {"status": "success", "ticket": ticket}

if __name__ == "__main__":
    # Run on 0.0.0.0 so the Linux server can reach it
    uvicorn.run("mt5_gateway:app", host="0.0.0.0", port=8001, reload=True)
