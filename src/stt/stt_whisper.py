import asyncio
import numpy as np
import io
import wave
import os
import time
import re
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
            await self.queue.put(audio_bytes)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

    async def run(self):
        """Process incoming 1-second chunks"""
        while self.running:
            chunk_bytes = await self.queue.get()
            if chunk_bytes is None: break
            
            # Convert to Float32
            audio_data = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # FIX 1: Increased Threshold (0.002 -> 0.005)
            # This ignores fan noise/breathing so we don't amplify it
            volume = np.abs(audio_data).mean()
            if volume < 0.005: 
                continue
            
            yield await self._transcribe_groq(chunk_bytes)

    async def _transcribe_groq(self, audio_bytes):
        if not GROQ_AVAILABLE or not self.client:
            return None

        # --- FIX 2: Smart Normalization (The "Hello" Killer) ---
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        max_val = np.abs(audio_np).max()
        
        # Only boost if the audio is "medium quiet" (2000-15000).
        # If it's < 2000, it's just background noise—DO NOT BOOST IT.
        if 2000 < max_val < 15000:
            target_level = 20000 
            scale = target_level / max_val
            audio_np = audio_np * scale
            audio_np = np.clip(audio_np, -32768, 32767)
            audio_bytes = audio_np.astype(np.int16).tobytes()
        # -------------------------------------------------------

        # Create virtual WAV
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) 
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        
        wav_io.seek(0)
        wav_io.name = "audio.wav"

        try:
            transcription = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                file=(wav_io.name, wav_io.read()),
                model="whisper-large-v3",
                prompt=f"Context: {self.prev_text[-100:]}", 
                response_format="json",
                language="en",
                temperature=0.0 
            )
            
            text = transcription.text.strip()
            
            # --- FIX 3: Aggressive Filtering ---
            if not text or not re.search(r'[a-zA-Z]', text):
                return None

            # Filter "Hello" loops and hallucinations
            text_lower = text.lower().strip('.!?')
            hallucinations = [
                "i can't hear you", "thank you", "you", "copyright", "bye", 
                "unsure", "hello", "hi", "oh", "okay"
            ]
            
            # If the text is JUST "Hello" (or strictly in the list above), ignore it.
            # Real users usually say "Hello, I have an emergency" or "Help".
            if text_lower in hallucinations:
                return None
            
            # -----------------------------------

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