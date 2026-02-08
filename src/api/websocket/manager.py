from typing import List, Dict
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Active dashboard connections
        self.dashboard_connections: List[WebSocket] = []
        
        # Active operator connections {operator_id: WebSocket}
        self.operator_connections: Dict[str, WebSocket] = {}
        
        # Active audio stream connections {call_id: WebSocket}
        self.audio_connections: Dict[str, WebSocket] = {}
    
    async def connect_dashboard(self, websocket: WebSocket):
        """Connect a dashboard client"""
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        print(f"Dashboard connected. Total: {len(self.dashboard_connections)}")
    
    def disconnect_dashboard(self, websocket: WebSocket):
        """Disconnect a dashboard client"""
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
            print(f"Dashboard disconnected. Total: {len(self.dashboard_connections)}")
    
    async def connect_operator(self, operator_id: str, websocket: WebSocket):
        """Connect an operator console"""
        await websocket.accept()
        self.operator_connections[operator_id] = websocket
        print(f"Operator {operator_id} connected")
    
    def disconnect_operator(self, operator_id: str):
        """Disconnect an operator console"""
        if operator_id in self.operator_connections:
            del self.operator_connections[operator_id]
            print(f"Operator {operator_id} disconnected")
    
    async def connect_audio(self, call_id: str, websocket: WebSocket):
        """Connect an audio stream for a call"""
        await websocket.accept()
        self.audio_connections[call_id] = websocket
        print(f"Audio stream connected for call {call_id}")
    
    def disconnect_audio(self, call_id: str):
        """Disconnect an audio stream"""
        if call_id in self.audio_connections:
            del self.audio_connections[call_id]
            print(f"Audio stream disconnected for call {call_id}")
    
    async def broadcast_to_dashboards(self, data: dict):
        """
        Broadcast data to all connected dashboards
        
        Args:
            data: Dictionary to send as JSON
        """
        if not self.dashboard_connections:
            return
        
        message = json.dumps(data)
        
        # Send to all connected dashboards
        disconnected = []
        for websocket in self.dashboard_connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending to dashboard: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_dashboard(ws)
    
    async def send_to_operator(self, operator_id: str, data: dict):
        """
        Send data to specific operator
        
        Args:
            operator_id: Operator to send to
            data: Dictionary to send as JSON
        """
        if operator_id in self.operator_connections:
            try:
                message = json.dumps(data)
                await self.operator_connections[operator_id].send_text(message)
            except Exception as e:
                print(f"Error sending to operator {operator_id}: {e}")
                self.disconnect_operator(operator_id)
    
    async def send_audio(self, call_id: str, audio_data: bytes):
        """
        Send audio data to caller
        
        Args:
            call_id: Call ID
            audio_data: Audio bytes
        """
        if call_id in self.audio_connections:
            try:
                await self.audio_connections[call_id].send_bytes(audio_data)
            except Exception as e:
                print(f"Error sending audio to call {call_id}: {e}")
                self.disconnect_audio(call_id)