from fastapi import WebSocket, WebSocketDisconnect
from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
from src.stt.stt_whisper import StreamingSTT
import asyncio
import re

async def audio_stream_endpoint(
    websocket: WebSocket,
    call_id: str,
    manager: ConnectionManager,
    orchestrator: CallOrchestrator
):
    # 1. Connect Victim
    await manager.connect_audio(call_id, websocket)
    
    # 2. Setup AI
    stt = StreamingSTT(model_size="distil-large-v3") 
    
    # 3. Create/Sync Call
    call = await orchestrator.create_incoming_call(caller_phone=f"User-{call_id[-4:]}")
    if call.id != call_id and call.id in orchestrator.active_calls:
        # Sync IDs if orchestrator created a new one
        real_call = orchestrator.active_calls.pop(call.id)
        real_call.id = call_id
        orchestrator.active_calls[call_id] = real_call
        call = real_call

    # Initial Greeting
    if call.assigned_to == "AI_AGENT":
        await websocket.send_json({"type": "ai_speech", "text": "911, what is your emergency?"})

    async def process_transcriptions():
        """Listen to the call and update dashboard text"""
        last_text = ""
        
        async for stt_result in stt.run():
            text = stt_result.get("text", "").strip()
            
            # --- FIX 1: Hallucination Filter ---
            # 1. Must contain at least one letter (ignores ".", "...", "?")
            if not re.search(r'[a-zA-Z]', text): 
                continue
            
            # 2. Ignore common Whisper hallucinations
            hallucinations = ["i can't hear you", "thank you", "you", "copyright", "bye"]
            if text.lower().strip('.!?') in hallucinations:
                continue
                
            # 3. Dedup (Ignore exact repeats)
            if text.lower() == last_text.lower():
                continue
            last_text = text
            # -----------------------------------

            try:
                # Update Dashboard & Get AI Response
                ai_response = await orchestrator.handle_caller_message(call_id, text)
                
                # --- FIX 2: Prevent Crash if Socket Closed ---
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_json({"type": "transcription", "text": text})
                    
                    if ai_response:
                        await websocket.send_json({"type": "ai_speech", "text": ai_response})
            except Exception as e:
                # Silent fail if socket closed during send
                break

    # Start Transcription Loop
    task = asyncio.create_task(process_transcriptions())

    try:
        while True:
            data = await websocket.receive()
            
            if data["type"] == "websocket.disconnect":
                break
            
            if "bytes" in data:
                audio_bytes = data["bytes"]
                await stt.push_audio(audio_bytes)
                
                # Route Audio to Human if assigned
                if call.assigned_to and call.assigned_to != "AI_AGENT":
                    await orchestrator.route_audio_victim_to_operator(call.id, audio_bytes)

    except Exception as e:
        print(f"Victim Stream Error: {e}")
    finally:
        # Cleanup
        manager.disconnect_audio(call_id)
        await stt.stop()