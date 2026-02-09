from fastapi import WebSocket, WebSocketDisconnect
from .manager import ConnectionManager
from src.core.orchestrator import CallOrchestrator
from src.stt.stt_whisper import StreamingSTT
import asyncio
import re

async def audio_stream_endpoint(
    websocket: WebSocket,
    call_id: str,
    manager: ConnectionManager,
    orchestrator: CallOrchestrator
):
    await manager.connect_audio(call_id, websocket)
    stt = StreamingSTT(model_size="distil-large-v3") 
    response_task = None
    
    # Track last message to prevent echoing
    last_processed_text = ""

    try:
        # ID Sync Logic
        if call_id not in orchestrator.active_calls:
            print(f"📞 Creating new session for Frontend ID: {call_id}")
            new_call = await orchestrator.create_incoming_call(caller_phone=f"Web-{call_id[-4:]}")
            internal_id = new_call.id
            if internal_id != call_id:
                if internal_id in orchestrator.active_calls:
                    call_obj = orchestrator.active_calls.pop(internal_id) 
                    call_obj.id = call_id
                    orchestrator.active_calls[call_id] = call_obj

        await websocket.send_json({"type": "ai_speech", "text": "911, what is your emergency?"})

        async def process_transcriptions():
            nonlocal last_processed_text
            try:
                async for stt_result in stt.run():
                    if stt_result is None: continue

                    text = stt_result.get("text", "").strip()
                    
                    # --- FIX 1: Aggressive "Real Word" Filter ---
                    # Must contain at least one alphabetical character (a-z)
                    # This kills ".", "...", "123", "?", etc.
                    if not re.search(r'[a-zA-Z]', text):
                        continue
                        
                    # Ignore short 1-letter noise (unless it's "I")
                    if len(text) < 2 and text.upper() != "I":
                        continue
                    # ---------------------------------------------
                    
                    # Dedup Logic
                    if text.lower() == last_processed_text.lower():
                        continue
                    last_processed_text = text

                    print(f"🎤 User ({call_id}): {text}")
                    
                    try:
                        await websocket.send_json({"type": "transcription", "text": text})

                        # Get AI Response
                        ai_response = await orchestrator.handle_caller_message(call_id, text)
                        
                        if ai_response:
                            print(f"🤖 AI: {ai_response}")
                            await websocket.send_json({"type": "ai_speech", "text": ai_response})
                        
                    except RuntimeError:
                        break 
                    except Exception as inner_e:
                        print(f"❌ Error processing message: {inner_e}")
                            
            except Exception as e:
                print(f"❌ Transcription Loop Failed: {e}")

        response_task = asyncio.create_task(process_transcriptions())

        while True:
            try:
                data = await websocket.receive()
                if data["type"] == "websocket.disconnect":
                    break
                if "bytes" in data:
                    await stt.push_audio(data["bytes"])
            except RuntimeError:
                break
            except Exception:
                break

    except Exception as e:
        print(f"Stream Error: {e}")
    finally:
        await stt.stop()
        if response_task:
            response_task.cancel()
        manager.disconnect_audio(call_id)