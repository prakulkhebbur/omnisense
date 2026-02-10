from fastapi import WebSocket, WebSocketDisconnect
from src.core.orchestrator import CallOrchestrator
from src.api.websocket.manager import ConnectionManager
from src.stt.stt_whisper import StreamingSTT
import asyncio
import re
import time

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
        old_call_id = call.id
        real_call = orchestrator.active_calls.pop(old_call_id)
        real_call.id = call_id
        orchestrator.active_calls[call_id] = real_call
        call = real_call
        orchestrator.call_queue = [
            call_id if cid == old_call_id else cid for cid in orchestrator.call_queue
        ]
        for op_data in orchestrator.operators.values():
            if op_data.get("current_call") == old_call_id:
                op_data["current_call"] = call_id
        await orchestrator._broadcast_update()

    # --- ECHO CANCELLATION STATE ---
    # Shared state to block mic when AI is talking
    echo_state = {"mute_until": 0}

    def mute_mic_for_ai_speech(text):
        """Calculate how long to ignore mic input based on text length"""
        word_count = len(text.split())
        # Estimate: 2.5 words per second + 1.0s buffer for network/latency
        duration = (word_count / 2.5) + 1.0
        echo_state["mute_until"] = time.time() + duration
        print(f"🔇 AI Speaking: Muting mic for {duration:.2f}s")

    # Initial Greeting
    if call.assigned_to == "AI_AGENT":
        greeting = "911, what is your emergency?"
        await websocket.send_json({"type": "ai_speech", "text": greeting})
        mute_mic_for_ai_speech(greeting)

    async def process_transcriptions():
        """Listen to the call and update dashboard text"""
        last_text = ""
        
        async for stt_result in stt.run():
            # --- FIX: Handle None (Silence/Hallucination) ---
            if not stt_result:
                continue
            # ------------------------------------------------

            text = stt_result.get("text", "").strip()
            
            # --- Hallucination Filter ---
            if not re.search(r'[a-zA-Z]', text): 
                continue
            
            hallucinations = ["i can't hear you", "thank you", "you", "copyright", "bye", "unsure"]
            if text.lower().strip('.!?') in hallucinations:
                continue
                
            if text.lower() == last_text.lower():
                continue
            last_text = text
            # ----------------------------

            try:
                # Update Dashboard & Get AI Response
                ai_response = await orchestrator.handle_caller_message(call_id, text)
                
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_json({"type": "transcription", "text": text})
                    
                    if ai_response:
                        await websocket.send_json({"type": "ai_speech", "text": ai_response})
                        # --- TRIGGER MUTE ---
                        mute_mic_for_ai_speech(ai_response)
                        
            except Exception as e:
                break

    # Start Transcription Loop
    task = asyncio.create_task(process_transcriptions())

    try:
        while True:
            data = await websocket.receive()
            
            if data["type"] == "websocket.disconnect":
                break
            
            if "bytes" in data:
                # --- ECHO GATE ---
                # If AI is currently speaking (plus buffer), drop audio packets
                if time.time() < echo_state["mute_until"]:
                    continue 

                audio_bytes = data["bytes"]
                await stt.push_audio(audio_bytes)
                
                # Route Audio to Human if assigned
                if call.assigned_to and call.assigned_to != "AI_AGENT":
                    await orchestrator.route_audio_victim_to_operator(call.id, audio_bytes)

    except Exception as e:
        print(f"Victim Stream Error: {e}")
    finally:
        manager.disconnect_audio(call_id)
        await stt.stop()
        await orchestrator.handle_caller_disconnect(call_id)