from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json

from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
from src.api.websocket.dashboard import dashboard_endpoint
from src.api.websocket.audio_stream import audio_stream_endpoint

app = FastAPI(title="OmniSense API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
orchestrator = CallOrchestrator()
orchestrator.set_broadcast_function(manager.broadcast_dashboard)

# --- PAGE ROUTES ---
@app.get("/")
async def get_dashboard(): return FileResponse("static/index.html")

@app.get("/caller")
async def get_caller(): return FileResponse("static/caller.html")

@app.get("/operator")
async def get_operator(): return FileResponse("static/operator.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup(): await orchestrator.start()

@app.on_event("shutdown")
async def shutdown(): await orchestrator.stop()

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
            # --- FIX: Handle Text (Commands) AND Bytes (Audio) ---
            message = await websocket.receive()
            
            if message["type"] == "websocket.receive":
                if "bytes" in message:
                    # Audio Data -> Relay to Victim
                    await orchestrator.route_audio_operator_to_victim(operator_id, message["bytes"], manager)
                
                elif "text" in message:
                    # JSON Command -> Handle Logic (Pick Up / Switch)
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
                        
            elif message["type"] == "websocket.disconnect":
                break
                
    except Exception as e:
        print(f"Operator Error: {e}")
    finally:
        await orchestrator.unregister_operator(operator_id)
