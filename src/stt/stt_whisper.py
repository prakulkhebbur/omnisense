import asyncio
import numpy as np
import io
import wave
import os
import time
from datetime import datetime, timezone

# Global Groq Client
_GROQ_CLIENT = None

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("❌ Groq library not found.")

class StreamingSTT:
    def __init__(self, model_size="distil-large-v3", device="cpu", compute_type="int8"):
        global _GROQ_CLIENT
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if GROQ_AVAILABLE and _GROQ_CLIENT is None:
            if not self.api_key:
                print("⚠️ WARNING: GROQ_API_KEY missing!")
            _GROQ_CLIENT = Groq(api_key=self.api_key)
            print("🚀 Groq Client Initialized")
            
        self.client = _GROQ_CLIENT
        self.queue = asyncio.Queue()
        self.running = True
        self.prev_text = "" 

    async def push_audio(self, audio_bytes):
        """Receive 1-second Int16 audio chunk from Client"""
        if self.running:
            # Add to processing queue
            await self.queue.put(audio_bytes)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

    async def run(self):
        """Process incoming 1-second chunks"""
        while self.running:
            # Wait for the next 1-second chunk
            chunk_bytes = await self.queue.get()
            if chunk_bytes is None: break
            
            # Convert to Float32 to check volume/energy
            audio_data = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # 1. Volume Check (Lowered threshold to 0.005 to catch whispers)
            volume = np.abs(audio_data).mean()
            if volume < 0.005:
                # Silence - ignore this chunk to save API calls
                continue
            
            # 2. Transcribe this chunk
            yield await self._transcribe_groq(chunk_bytes)

    async def _transcribe_groq(self, audio_bytes):
        if not GROQ_AVAILABLE or not self.client:
            return None

        # Create virtual WAV file
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        
        wav_io.seek(0)
        wav_io.name = "audio.wav"

        try:
            # Send to Groq
            transcription = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                file=(wav_io.name, wav_io.read()),
                model="whisper-large-v3",
                prompt=f"Previous: {self.prev_text[-100:]}", # Context helps accuracy
                response_format="json",
                language="en",
                temperature=0.0
            )
            
            text = transcription.text.strip()
            if text:
                print(f"🗣️  Heard: {text}")
                self.prev_text += " " + text
                return {
                    "text": text,
                    "final": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            return None