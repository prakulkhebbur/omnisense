from fastapi import WebSocket, WebSocketDisconnect
from .manager import ConnectionManager
from src.core.orchestrator import CallOrchestrator
import asyncio
import json

async def audio_stream_endpoint(
    websocket: WebSocket,
    call_id: str,
    manager: ConnectionManager,
    orchestrator: CallOrchestrator
):
    """
    WebSocket endpoint for audio streaming
    Handles real-time audio from caller and sends AI responses
    
    Args:
        websocket: WebSocket connection
        call_id: ID of the call
        manager: Connection manager
        orchestrator: Call orchestrator
    """
    await manager.connect_audio(call_id, websocket)
    
    try:
        # Get the call
        call = orchestrator.active_calls.get(call_id)
        if not call:
            await websocket.close(code=4004, reason="Call not found")
            return
        
        # Send initial AI greeting
        initial_message = "911, what's your emergency?"
        await websocket.send_json({
            "type": "ai_speech",
            "text": initial_message
        })
        
        # Handle incoming messages
        while True:
            # Receive message from caller
            message = await websocket.receive_json()
            
            message_type = message.get("type")
            
            if message_type == "caller_speech":
                # Caller spoke - text transcribed by frontend
                caller_text = message.get("text")
                
                if caller_text:
                    # AI processes and responds
                    ai_response = await orchestrator.handle_caller_message(
                        call_id, 
                        caller_text
                    )
                    
                    # Send AI response back
                    await websocket.send_json({
                        "type": "ai_speech",
                        "text": ai_response
                    })
                    
                    # Check if call should be queued
                    updated_call = orchestrator.active_calls.get(call_id)
                    if updated_call and updated_call.status.value == "queued":
                        # Call moved to queue
                        await websocket.send_json({
                            "type": "call_queued",
                            "message": "Your call has been prioritized. An operator will assist you shortly."
                        })
                        break
            
            elif message_type == "audio_chunk":
                # Raw audio data (for future STT integration)
                # For now, we'll handle text-based for simplicity
                pass
    
    except WebSocketDisconnect:
        manager.disconnect_audio(call_id)
    except Exception as e:
        print(f"Audio stream error for call {call_id}: {e}")
        manager.disconnect_audio(call_id)