import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
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
    "status": "Running",
    "equity": "$0.00",
    "last_logic": "Waiting for AI analysis...",
    "last_confidence": "0%",
    "trade_history": []
}

async def trading_loop():
    print("AI Hedge Fund Bot Started...")
    while True:
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Running Trading Cycle...")
            
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
                    "time": datetime.datetime.now().strftime("%H:%M:%S"),
                    "asset": config.SYMBOL,
                    "signal": signal,
                    "logic": logic,
                    "pnl": 0 # PNL is 0 upon execution
                }
                bot_state["trade_history"].insert(0, trade)
            else:
                print(f"Signal: HOLD | Logic: {logic}")
            
        except Exception as e:
            print(f"Error in trading loop: {e}")
            
        # Run every 5 minutes (300 seconds) for standard interval
        await asyncio.sleep(300) 

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
