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
    
    # 2. Setup AI (Always runs for transcription)
    stt = StreamingSTT(model_size="distil-large-v3") 
    
    # 3. Create Call
    call = await orchestrator.create_incoming_call(caller_phone=f"User-{call_id[-4:]}")
    
    # ID Sync Fix
    if call.id != call_id:
        if call.id in orchestrator.active_calls:
            real_call = orchestrator.active_calls.pop(call.id)
            real_call.id = call_id
            orchestrator.active_calls[call_id] = real_call
            call = real_call

    # Initial AI Greeting (Only if assigned to AI)
    if call.assigned_to == "AI_AGENT":
        await websocket.send_json({"type": "ai_speech", "text": "911, what is your emergency?"})

    async def process_transcriptions():
        """Listen to the call and update dashboard text"""
        async for stt_result in stt.run():
            text = stt_result.get("text", "").strip()
            
            # Filter noise
            if not text or not re.search(r'[a-zA-Z]', text): continue
            
            # Update Dashboard Transcript
            # Note: This updates the transcript AND gets an AI response if needed
            ai_response = await orchestrator.handle_caller_message(call_id, text)
            
            # Send Transcript to Victim UI
            await websocket.send_json({"type": "transcription", "text": text})

            # If AI replied (because no human is assigned), send TTS
            if ai_response:
                await websocket.send_json({"type": "ai_speech", "text": ai_response})

    # Start Transcription Loop
    asyncio.create_task(process_transcriptions())

    try:
        while True:
            data = await websocket.receive()
            
            if data["type"] == "websocket.disconnect":
                print(f"Victim {call_id} disconnected.")
                break
            
            if "bytes" in data:
                audio_bytes = data["bytes"]
                
                # A. Send to STT (Always transcribe for records)
                await stt.push_audio(audio_bytes)
                
                # B. Route Audio to Human (if assigned)
                if call.assigned_to and call.assigned_to != "AI_AGENT":
                    # ROUTE TO OPERATOR
                    await orchestrator.route_audio_victim_to_operator(call.id, audio_bytes)
                else:
                    # AI Mode (STT loop handles logic above)
                    pass

    except Exception as e:
        print(f"Victim Stream Error: {e}")
    finally:
        await manager.disconnect_audio(call_id)
        await stt.stop()