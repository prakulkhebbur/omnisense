import asyncio
import numpy as np
from faster_whisper import WhisperModel
from datetime import datetime, timezone

class StreamingSTT:
    def __init__(self, model_size="small.en", device="cpu", compute_type="int8"):
        # The VAD filter is crucial for accuracy as it ignores background noise
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.queue = asyncio.Queue()
        self.running = True
        self.sample_rate = 16000

    async def push_audio(self, audio_bytes):
        if self.running:
            # Whisper requires float32 normalized between -1 and 1
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
            
            # Process every 2-3 seconds of audio to maintain context and accuracy
            if len(audio_buffer) >= 8: 
                full_audio = np.concatenate(audio_buffer)
                
                # vad_filter=True prevents the model from hallucinating during silence
                segments, _ = self.model.transcribe(full_audio, beam_size=5, vad_filter=True)
                
                for segment in segments:
                    if segment.text.strip():
                        yield {
                            "text": segment.text.strip(),
                            "final": True,
                            "time": datetime.now(timezone.utc).isoformat()
                        }
                # Keep the last second of audio to provide context for the next chunk
                audio_buffer = audio_buffer[-4:]