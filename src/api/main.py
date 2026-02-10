from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json
import asyncio
from pathlib import Path
import os

from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
from src.api.websocket.dashboard import dashboard_endpoint
from src.api.websocket.audio_stream import audio_stream_endpoint

# --- FIX 1: ABSOLUTE PATHS SETUP ---
# This ensures Python finds 'static' even if you run from master_run.py
CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent.parent  # Go up to 'omnisense' root
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="OmniSense API")

# --- FIX 2: ALLOW LOCAL NETWORK ACCESS (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
orchestrator = CallOrchestrator()

# Connect Orchestrator to Dashboard Broadcast
# Wrapper ensures we await the async method correctly
async def broadcast_wrapper(state):
    # Check if method is broadcast_dashboard or broadcast_dashboard_update
    if hasattr(manager, "broadcast_dashboard"):
        await manager.broadcast_dashboard(state)
    elif hasattr(manager, "broadcast_dashboard_update"):
        await manager.broadcast_dashboard_update(state)

orchestrator.set_broadcast_function(broadcast_wrapper)
orchestrator.set_manager(manager)

# --- LINK ORCHESTRATOR TO ROUTES ---
# This is crucial so your HTTP endpoints can access the active calls
from src.api.routes import calls, operators
calls.orchestrator = orchestrator
operators.set_orchestrator(orchestrator)

# Register API routers
app.include_router(calls.router)
app.include_router(operators.router)

# --- FIX 3: EXPLICIT PAGE ROUTES WITH ABSOLUTE PATHS ---
@app.get("/")
async def get_dashboard():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/caller")
async def get_caller():
    return FileResponse(STATIC_DIR / "caller.html")

@app.get("/operator")
async def get_operator():
    return FileResponse(STATIC_DIR / "operator.html")

# Mount Static Files (CSS, JS)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    print(f"⚠️ WARNING: Static directory not found at {STATIC_DIR}")

@app.on_event("startup")
async def startup():
    await orchestrator.start()

@app.on_event("shutdown")
async def shutdown():
    await orchestrator.stop()

# --- WEBSOCKETS ---
@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await dashboard_endpoint(websocket, manager, orchestrator)

@app.websocket("/ws/audio/{call_id}")
async def ws_audio(websocket: WebSocket, call_id: str):
    await audio_stream_endpoint(websocket, call_id, manager, orchestrator)

@app.websocket("/ws/operator/{operator_id}")
async def ws_operator(websocket: WebSocket, operator_id: str):
    await websocket.accept()
    await orchestrator.register_operator(operator_id, websocket)
    
    try:
        while True:
            # Receive generic message (Text or Bytes)
            message = await websocket.receive()
            
            # Case A: Audio Data (Bytes) -> Relay to Victim
            if "bytes" in message:
                await orchestrator.route_audio_operator_to_victim(operator_id, message["bytes"], manager)
            
            # Case B: JSON Command (Text) -> Pickup/Complete
            elif "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "pickup_call":
                        call_id = data.get("call_id")
                        print(f"👨‍💼 Operator {operator_id} requesting pickup of {call_id}")
                        await orchestrator.force_assign_operator(call_id, operator_id)
                        
                    elif data.get("type") == "complete_call":
                        print(f"✅ Operator {operator_id} completed current call")
                        await orchestrator.complete_call(operator_id, manager)
                except Exception as e:
                    print(f"Command Error: {e}")
            
            # Case C: Disconnect
            elif message["type"] == "websocket.disconnect":
                break
                
    except Exception as e:
        print(f"Operator Error: {e}")
    finally:
        await orchestrator.unregister_operator(operator_id)

# if __name__ == "__main__":
#     import uvicorn
#     # Use 0.0.0.0 so you can access it from other devices
#     uvicorn.run(app, host="0.0.0.0", port=8000)