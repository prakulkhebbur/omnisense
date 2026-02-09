from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
from src.api.websocket.dashboard import dashboard_websocket_endpoint
from src.api.websocket.audio_stream import audio_stream_endpoint
from src.api.routes import calls, operators

# Global instances
orchestrator = CallOrchestrator()
connection_manager = ConnectionManager()

# Set broadcast function for orchestrator
async def broadcast_state(state: dict):
    """Broadcast state to all dashboards"""
    await connection_manager.broadcast_to_dashboards(state)

orchestrator.set_broadcast_function(broadcast_state)

# Set orchestrator in route modules
calls.set_orchestrator(orchestrator)
operators.set_orchestrator(orchestrator)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 OmniSense API Server Starting...")
    print("📡 WebSocket Server Ready")
    print("🎯 Orchestrator Initialized")

    from src.stt.stt_whisper import StreamingSTT
    print("⚙️  Pre-initializing AI Model...")
    # This triggers the global load immediately
    StreamingSTT(model_size="distil-small.en")

    yield
    # Shutdown
    print("🛑 OmniSense API Server Shutting Down...")

# Create FastAPI app
app = FastAPI(
    title="OmniSense Emergency Call System",
    description="AI-powered emergency call management system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CallOrchestrator()
connection_manager = ConnectionManager()

async def broadcast_state(state: dict):
    await connection_manager.broadcast_to_dashboards(state)

orchestrator.set_broadcast_function(broadcast_state)
calls.set_orchestrator(orchestrator)
operators.set_orchestrator(orchestrator)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 OmniSense API Server Starting...")
    yield
    print("🛑 OmniSense API Server Shutting Down...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Include Routers
app.include_router(calls.router)
app.include_router(operators.router)

# 2. WebSocket Endpoints
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await dashboard_websocket_endpoint(websocket, connection_manager)

@app.websocket("/ws/audio/{call_id}")
async def websocket_audio(websocket: WebSocket, call_id: str):
    await audio_stream_endpoint(websocket, call_id, connection_manager, orchestrator)

@app.get("/api/state")
async def get_system_state():
    return orchestrator.get_state()

# 3. MOUNT STATIC FILES (Serve the Frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.websocket("/ws/operator/{operator_id}")
async def ws_operator(websocket: WebSocket, operator_id: str):
    await websocket.accept()
    
    # Register Op in Orchestrator
    await orchestrator.register_operator(operator_id, websocket)
    
    try:
        while True:
            # Receive Audio from Operator's Mic
            data = await websocket.receive_bytes()
            
            # Send to Victim (Relay via Manager)
            await orchestrator.route_audio_operator_to_victim(operator_id, data, manager)
            
    except WebSocketDisconnect:
        await orchestrator.unregister_operator(operator_id)
    except Exception as e:
        print(f"Operator Error: {e}")