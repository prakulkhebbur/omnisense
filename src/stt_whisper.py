import asyncio
import numpy as np
from faster_whisper import WhisperModel
from datetime import datetime, timezone

class StreamingSTT:
    def __init__(self, model_size="distil-large-v3", device="cpu", compute_type="int8"):
        # distil-large-v3 is 6-9x faster than the original large-v3
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.queue = asyncio.Queue()
        self.running = True
        self.sample_rate = 16000
        self.prev_text = "" # Stores context for better accuracy

    async def push_audio(self, audio_bytes):
        if self.running:
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            await self.queue.put(audio_data)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

    async def run(self):
        audio_buffer = []
        while True:
            chunk = await self.queue.get()
            if chunk is None: break
            
            audio_buffer.append(chunk)
            
            # Processing 3 seconds of audio (12 chunks of 250ms) ensures high accuracy
            if len(audio_buffer) >= 12: 
                full_audio = np.concatenate(audio_buffer)
                
                # vad_filter=True ignores background noise
                # initial_prompt uses previous text to help the model understand current context
                segments, _ = self.model.transcribe(
                    full_audio, 
                    beam_size=5, 
                    vad_filter=True,
                    initial_prompt=self.prev_text[-200:] 
                )
                
                for segment in segments:
                    if segment.text.strip():
                        current_text = segment.text.strip()
                        self.prev_text += " " + current_text
                        yield {
                            "text": current_text,
                            "final": True,
                            "time": datetime.now(timezone.utc).isoformat()
                        }
                
                # Keep the last 1 second for overlap to ensure words aren't cut in half
                audio_buffer = audio_buffer[-4:]