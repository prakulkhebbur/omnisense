from fastapi import WebSocket, WebSocketDisconnect
from .manager import ConnectionManager

async def dashboard_websocket_endpoint(
    websocket: WebSocket,
    manager: ConnectionManager
):
    """
    WebSocket endpoint for dashboard real-time updates
    
    Sends system state updates to connected dashboards
    """
    await manager.connect_dashboard(websocket)
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            # Receive message (dashboards might send commands)
            data = await websocket.receive_text()
            
            # Handle dashboard commands if needed
            # For now, just keep connection alive
            
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
    except Exception as e:
        print(f"Dashboard WebSocket error: {e}")
        manager.disconnect_dashboard(websocket)