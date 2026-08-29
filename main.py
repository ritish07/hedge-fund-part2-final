import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from contextlib import asynccontextmanager
import asyncio
import os
import datetime
import config
import data_engine
import ai_brain
import execution

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

bot_state = {
    "is_running": False,
    "interval": 30,
    "status": "System Offline",
    "equity": "$0.00",
    "last_logic": "Waiting for engine initialization...",
    "last_confidence": "0%",
    "trade_history": []
}

class ControlRequest(BaseModel):
    action: str
    interval: int

last_trade_time = datetime.datetime.now() - datetime.timedelta(days=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(trading_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.post("/api/control")
async def control_bot(req: ControlRequest):
    global last_trade_time
    bot_state["interval"] = req.interval
    if req.action == "start":
        bot_state["is_running"] = True
        bot_state["status"] = "System Online"
        bot_state["last_logic"] = "Initializing connection to AI backend..."
        last_trade_time = datetime.datetime.now() - datetime.timedelta(days=1)
    else:
        bot_state["is_running"] = False
        bot_state["status"] = "System Offline"
        bot_state["last_logic"] = "Engine stopped by user."
    return {"status": "success"}

async def trading_loop():
    global last_trade_time
    print("AI Hedge Fund Bot Ready...", flush=True)
    
    while True:
        now = datetime.datetime.now()
        
        if bot_state["is_running"] and (now - last_trade_time).total_seconds() >= bot_state["interval"]:
            try:
                print(f"\n[{now.strftime('%H:%M:%S')}] Running Trading Cycle...", flush=True)
                
                # Scan all symbols sequentially
                for symbol in config.SYMBOLS:
                    if not bot_state["is_running"]: 
                        break # Stop immediately if user clicked Stop
                        
                    print(f"-> Analyzing {symbol}...", flush=True)
                    bot_state["last_logic"] = f"Analyzing market structure for {symbol}..."
                    
                    # 1. Fetch Data in worker thread
                    data = await asyncio.to_thread(data_engine.fetch_multi_timeframe_data, symbol)
                    if data and 'equity' in data:
                        bot_state["equity"] = f"${data.get('equity', 0):,.2f}"
                    
                    # 2. AI Decision in worker thread
                    decision = await asyncio.to_thread(ai_brain.get_ai_decision, data, symbol)
                    
                    logic = decision.get("logic", "No logic provided")
                    confidence = decision.get("confidence_score", 0)
                    signal = decision.get("signal", "HOLD")
                    
                    bot_state["last_logic"] = f"[{symbol}] {logic}"
                    bot_state["last_confidence"] = f"{confidence}%"
                    
                    # 3. Execute in worker thread
                    if signal in ["BUY", "SELL"]:
                        exec_result = await asyncio.to_thread(execution.execute_trade, symbol, signal)
                        print(f"   Signal: {signal} | Result: {exec_result}", flush=True)
                        
                        trade = {
                            "time": datetime.datetime.now().strftime("%H:%M:%S"),
                            "asset": symbol,
                            "signal": signal,
                            "logic": logic,
                            "pnl": 0
                        }
                        bot_state["trade_history"].insert(0, trade)
                    else:
                        print(f"   Signal: HOLD", flush=True)
                        
                    # Brief pause between symbol API calls to avoid rate limiting
                    await asyncio.sleep(2)
                    
                last_trade_time = datetime.datetime.now()
                bot_state["last_logic"] = f"Cycle complete. Waiting for next interval..."
                
            except Exception as e:
                print(f"Error in trading loop: {e}", flush=True)
                last_trade_time = datetime.datetime.now()
                
        await asyncio.sleep(1) 

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/status")
async def get_status():
    return bot_state

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

