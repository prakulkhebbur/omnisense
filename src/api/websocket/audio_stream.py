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
    Handles: 
    1. Incoming Audio (Int16 PCM) -> Groq Whisper
    2. Transcription -> AI Agent (Groq Llama 3)
    3. AI Response -> Client (TTS)
    """
    await manager.connect_audio(call_id, websocket)
    
    # Initialize Server-Side STT (Groq Powered)
    # Ensure src/stt_whisper.py has the Groq updates applied
    stt = StreamingSTT(model_size="distil-large-v3") 
    
    response_task = None

    try:
        # --- 🚨 CRITICAL FIX: Sync Frontend ID with Backend ---
        if call_id not in orchestrator.active_calls:
            print(f"📞 Creating new session for Frontend ID: {call_id}")
            
            # 1. Create call (Returns the Call OBJECT with a random UUID)
            new_call = await orchestrator.create_incoming_call(caller_phone=f"Web-{call_id[-4:]}")
            internal_id = new_call.id  # Extract the UUID string
            
            # 2. If IDs don't match, force the swap so Frontend can find it
            if internal_id != call_id:
                print(f"🔄 Swapping Internal ID {internal_id} -> {call_id}")
                
                # Remove old UUID entry
                if internal_id in orchestrator.active_calls:
                    call_obj = orchestrator.active_calls.pop(internal_id) 
                    call_obj.id = call_id  # Update object ID to match Frontend
                    orchestrator.active_calls[call_id] = call_obj # Re-save under Frontend ID
        # -------------------------------------------------------------

        # Send initial AI greeting
        await websocket.send_json({
            "type": "ai_speech",
            "text": "911, what is your emergency?"
        })

        # --- Background Task: Process Transcriptions from STT ---
        async def process_transcriptions():
            # This loop waits for stt.run() to yield a full sentence (Speech-to-Text)
            async for stt_result in stt.run():
                text = stt_result.get("text", "")
                
                if text:
                    print(f"🎤 User ({call_id}): {text}")
                    
                    # 1. Send Transcription to UI (Visual feedback)
                    await websocket.send_json({
                        "type": "transcription",
                        "text": text
                    })

                    # 2. Get AI Response (Groq Llama 3 is fast!)
                    ai_response = await orchestrator.handle_caller_message(call_id, text)
                    
                    if ai_response:
                        print(f"🤖 AI: {ai_response}")
                        # 3. Send AI Text back to Client (Client handles TTS)
                        await websocket.send_json({
                            "type": "ai_speech",
                            "text": ai_response
                        })

                    # 4. Check Queue Status (Has this call been prioritized?)
                    call = orchestrator.active_calls.get(call_id)
                    if call and hasattr(call, 'status') and str(call.status.value) == "queued":
                        await websocket.send_json({
                            "type": "call_queued", 
                            "message": "Call prioritized. Waiting for operator."
                        })

        # Start the processing task
        response_task = asyncio.create_task(process_transcriptions())

        # --- Main Loop: Receive Audio Data from Client ---
        while True:
            # We expect bytes (audio) or text (control messages)
            data = await websocket.receive()
            
            if "bytes" in data:
                # Push raw Int16 PCM Audio to STT Buffer
                await stt.push_audio(data["bytes"])
            
            elif "text" in data:
                # Handle control messages (ping/pong) if needed
                pass

    except WebSocketDisconnect:
        print(f"❌ Client {call_id} disconnected")
    except Exception as e:
        print(f"⚠️ Error in audio stream: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await stt.stop()
        if response_task:
            response_task.cancel()
        manager.disconnect_audio(call_id)