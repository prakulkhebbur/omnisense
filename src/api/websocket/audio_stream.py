from fastapi import WebSocket, WebSocketDisconnect
from .manager import ConnectionManager
from src.core.orchestrator import CallOrchestrator
from src.stt_whisper import StreamingSTT
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
    """
    await manager.connect_audio(call_id, websocket)
    
    # Initialize Server-Side STT
    stt = StreamingSTT(model_size="distil-small.en") # Use small/base for faster CPU latency
    
    # Task to handle AI responses from STT stream
    response_task = None

    try:
        # Create/Get call in orchestrator
        if call_id not in orchestrator.active_calls:
            # For demo: create implicit incoming call if not exists
            await orchestrator.create_incoming_call(caller_phone=f"Unknown-{call_id[-4:]}")

        # Send initial greeting
        await websocket.send_json({
            "type": "ai_speech",
            "text": "911, what is your emergency?"
        })

        # Define the loop that processes transcribed text
        async def process_transcriptions():
            async for stt_result in stt.run():
                text = stt_result.get("text", "")
                if text:
                    print(f"User {call_id} said: {text}")
                    
                    # Send Transcription back to UI (so user sees what server heard)
                    await websocket.send_json({
                        "type": "transcription",
                        "text": text
                    })

                    # Get AI Response
                    ai_response = await orchestrator.handle_caller_message(call_id, text)
                    
                    # Send AI Audio/Text back
                    await websocket.send_json({
                        "type": "ai_speech",
                        "text": ai_response
                    })

                    # Check queue status
                    call = orchestrator.active_calls.get(call_id)
                    if call and str(call.status.value) == "queued":
                        await websocket.send_json({
                            "type": "call_queued", 
                            "message": "Call prioritized. Waiting for operator."
                        })

        # Start the processing task
        response_task = asyncio.create_task(process_transcriptions())

        # Main Loop: Receive Audio Data
        while True:
            # We expect bytes (audio) or text (control messages)
            data = await websocket.receive()
            
            if "bytes" in data:
                # Raw PCM Audio -> STT
                await stt.push_audio(data["bytes"])
            
            elif "text" in data:
                # Handle control messages if any
                pass

    except WebSocketDisconnect:
        print(f"Client {call_id} disconnected")
    except Exception as e:
        print(f"Error in audio stream: {e}")
    finally:
        await stt.stop()
        if response_task:
            response_task.cancel()
        manager.disconnect_audio(call_id)