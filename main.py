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

# Global state for the frontend dashboard
bot_state = {
    "is_running": False,
    "interval": 30, # Default to 30 seconds
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
    last_trade_time = datetime.datetime.now() - datetime.timedelta(days=1) # Force immediate run on start
    
    while True:
        now = datetime.datetime.now()
        
        # Check if bot is running AND the interval has passed
        if bot_state["is_running"] and (now - last_trade_time).total_seconds() >= bot_state["interval"]:
            try:
                print(f"[{now.strftime('%H:%M:%S')}] Running Trading Cycle...")
                
                # 1. Fetch Data
                data = data_engine.fetch_multi_timeframe_data()
                bot_state["equity"] = f"${data.get('equity', 0):,.2f}"
                
                # 2. Get AI Decision
                decision = ai_brain.analyze_market(data)
                
                logic = decision.get("logic", "No logic provided")
                confidence = decision.get("confidence_score", 0)
                signal = decision.get("signal", "HOLD")
                
                bot_state["last_logic"] = logic
                bot_state["last_confidence"] = f"{confidence}%"
                
                # 3. Execute
                if signal in ["BUY", "SELL"]:
                    exec_result = execution.execute_trade(signal)
                    print(f"Signal: {signal} | Result: {exec_result}")
                    
                    # Append to history for the UI Graph
                    trade = {
                        "time": now.strftime("%H:%M:%S"),
                        "asset": config.SYMBOL,
                        "signal": signal,
                        "logic": logic,
                        "pnl": 0 # PNL is 0 upon execution
                    }
                    bot_state["trade_history"].insert(0, trade)
                else:
                    print(f"Signal: HOLD | Logic: {logic}")
                    
                # Update last trade time after a successful cycle
                last_trade_time = datetime.datetime.now()
                
            except Exception as e:
                print(f"Error in trading loop: {e}")
                last_trade_time = datetime.datetime.now() # Reset time even on error to prevent spam
                
        # Sleep briefly to keep the loop responsive to Stop commands
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
