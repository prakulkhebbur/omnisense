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
        # Build an initial state consistent with orchestrator._broadcast_update
        active_calls = [c.model_dump(mode='json') for c in orchestrator.active_calls.values() if c.status == c.status.IN_PROGRESS]
        completed = [c.model_dump(mode='json') for c in orchestrator.active_calls.values() if c.status == c.status.COMPLETED]

        pending = []
        for cid in orchestrator.call_queue:
            call = orchestrator.active_calls.get(cid)
            if call:
                pending.append(call.model_dump(mode='json'))

        operators_state = {}
        for op_id, op in orchestrator.operators.items():
            model = op.get('model') if isinstance(op, dict) else None
            operators_state[op_id] = {
                'status': model.status.value if model else 'UNKNOWN',
                'current_call': op.get('current_call') if isinstance(op, dict) else None
            }

        initial_state = {
            "active_calls": active_calls,
            "completed_calls": completed,
            "pending_calls": pending,
            "operators": operators_state,
            "stats": {"total_active": len(active_calls), "completed": len(completed), "queued": len(pending)}
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