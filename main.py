import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import config
import data_engine
import ai_brain
import execution
import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

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

@app.post("/api/control")
async def control_bot(req: ControlRequest):
    bot_state["interval"] = req.interval
    if req.action == "start":
        bot_state["is_running"] = True
        bot_state["status"] = "System Online"
        bot_state["last_logic"] = "Initializing connection to AI backend..."
    else:
        bot_state["is_running"] = False
        bot_state["status"] = "System Offline"
        bot_state["last_logic"] = "Engine stopped by user."
    return {"status": "success"}

async def trading_loop():
    print("AI Hedge Fund Bot Ready...")
    last_trade_time = datetime.datetime.now() - datetime.timedelta(days=1)
    
    while True:
        now = datetime.datetime.now()
        
        if bot_state["is_running"] and (now - last_trade_time).total_seconds() >= bot_state["interval"]:
            try:
                print(f"\n[{now.strftime('%H:%M:%S')}] Running Trading Cycle...")
                
                # Scan all symbols sequentially
                for symbol in config.SYMBOLS:
                    if not bot_state["is_running"]: 
                        break # Stop immediately if user clicked Stop
                        
                    print(f"-> Analyzing {symbol}...")
                    bot_state["last_logic"] = f"Analyzing market structure for {symbol}..."
                    
                    # 1. Fetch Data
                    data = data_engine.fetch_multi_timeframe_data(symbol)
                    if data and 'equity' in data:
                        bot_state["equity"] = f"${data.get('equity', 0):,.2f}"
                    
                    # 2. AI Decision
                    decision = ai_brain.get_ai_decision(data, symbol)
                    
                    logic = decision.get("logic", "No logic provided")
                    confidence = decision.get("confidence_score", 0)
                    signal = decision.get("signal", "HOLD")
                    
                    bot_state["last_logic"] = f"[{symbol}] {logic}"
                    bot_state["last_confidence"] = f"{confidence}%"
                    
                    # 3. Execute
                    if signal in ["BUY", "SELL"]:
                        exec_result = execution.execute_trade(symbol, signal)
                        print(f"   Signal: {signal} | Result: {exec_result}")
                        
                        trade = {
                            "time": datetime.datetime.now().strftime("%H:%M:%S"),
                            "asset": symbol,
                            "signal": signal,
                            "logic": logic,
                            "pnl": 0
                        }
                        bot_state["trade_history"].insert(0, trade)
                    else:
                        print(f"   Signal: HOLD")
                        
                    # Brief pause between symbol API calls to avoid rate limiting
                    await asyncio.sleep(2)
                    
                last_trade_time = datetime.datetime.now()
                bot_state["last_logic"] = f"Cycle complete. Waiting for next interval..."
                
            except Exception as e:
                print(f"Error in trading loop: {e}")
                last_trade_time = datetime.datetime.now()
                
        await asyncio.sleep(1) 

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trading_loop())

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return bot_state

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
