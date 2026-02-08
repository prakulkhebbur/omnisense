from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

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

# Include routers
app.include_router(calls.router)
app.include_router(operators.router)

# WebSocket endpoints
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates"""
    await dashboard_websocket_endpoint(websocket, connection_manager)

@app.websocket("/ws/audio/{call_id}")
async def websocket_audio(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for audio streaming"""
    await audio_stream_endpoint(websocket, call_id, connection_manager, orchestrator)

# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OmniSense Emergency Call System",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "active_calls": len(orchestrator.active_calls),
        "operators": len(orchestrator.operators),
        "queue_size": orchestrator.queue_manager.get_queue_size(),
        "dashboard_connections": len(connection_manager.dashboard_connections)
    }

@app.get("/api/state")
async def get_system_state():
    """Get current system state (for debugging)"""
    return orchestrator.get_state()