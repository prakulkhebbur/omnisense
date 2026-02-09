from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
import asyncio

async def dashboard_endpoint(
    websocket: WebSocket,
    manager: ConnectionManager,
    orchestrator: CallOrchestrator
):
    """
    Handles the Dashboard WebSocket connection.
    1. Connects the dashboard.
    2. Sends the INITIAL state immediately.
    3. Keeps the connection open to receive 'ping' or other commands.
    """
    await manager.connect_dashboard(websocket)
    
    try:
        # 1. Send Initial State immediately upon connection
        queue_objects = []
        for cid in orchestrator.call_queue:
            if cid in orchestrator.active_calls:
                queue_objects.append(orchestrator.active_calls[cid].dict())

        initial_state = {
            "active_calls": [c.dict() for c in orchestrator.active_calls.values()],
            "queue": queue_objects,
            "operators": {op_id: op['current_call'] for op_id, op in orchestrator.operators.items()},
            "stats": {
                "total_active": len(orchestrator.active_calls),
                "queued": len(orchestrator.call_queue)
            }
        }
        await websocket.send_json(jsonable_encoder(initial_state))

        # 2. Keep connection alive
        while True:
            # We don't really expect much data FROM the dashboard,
            # but we need to await receive() to keep the socket open.
            data = await websocket.receive_text()
            
            # Optional: Handle "force_refresh" command if you build a refresh button
            if data == "refresh":
                await orchestrator._broadcast_update()

    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
    except Exception as e:
        print(f"Dashboard Error: {e}")
        manager.disconnect_dashboard(websocket)