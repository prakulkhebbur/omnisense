from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    """
    Manages all WebSocket connections (Dashboard & Audio Streams).
    Acts as the 'Switch' for routing data.
    """
    def __init__(self):
        # Dashboard Observers (Read-Only)
        self.dashboard_connections: List[WebSocket] = []
        
        # Audio Streams (Active Calls)
        # {call_id: websocket}
        self.audio_connections: Dict[str, WebSocket] = {}

    # --- DASHBOARD (PRESERVED) ---
    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)

    async def broadcast_dashboard(self, data: dict):
        """Push updates to all open dashboards"""
        for connection in self.dashboard_connections:
            try:
                await connection.send_json(data)
            except:
                pass

    # --- AUDIO STREAMING (NEW + PRESERVED) ---
    async def connect_audio(self, call_id: str, websocket: WebSocket):
        """Register a victim's audio socket"""
        await websocket.accept()
        self.audio_connections[call_id] = websocket
        print(f"🔌 Audio stream connected for call {call_id}")

    def disconnect_audio(self, call_id: str):
        """Unregister a victim"""
        if call_id in self.audio_connections:
            del self.audio_connections[call_id]
            print(f"🔌 Audio stream disconnected for call {call_id}")

    async def send_audio_to_victim(self, call_id: str, audio_bytes: bytes):
        """
        RELAY: Operator Voice -> Victim
        Used by the Orchestrator to route operator audio.
        """
        websocket = self.audio_connections.get(call_id)
        if websocket:
            try:
                await websocket.send_bytes(audio_bytes)
            except Exception as e:
                print(f"Error relaying audio to victim {call_id}: {e}")