import asyncio
import numpy as np
import io
import wave
import os
import time
from datetime import datetime, timezone

# Try importing Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("❌ Groq library not found. Install with: pip install groq")

class StreamingSTT:
    """
    Async Speech-to-Text using Groq API (Whisper Large V3)
    """
    def __init__(self, model_size="distil-large-v3", device="cpu", compute_type="int8"):
        # Note: model_size args are ignored here as we use Groq's API model
        
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("⚠️ WARNING: GROQ_API_KEY not found in environment variables!")
        
        if GROQ_AVAILABLE:
            self.client = Groq(api_key=self.api_key)
            print("🚀 Connected to Groq for Whisper (STT)")
        
        self.queue = asyncio.Queue()
        self.running = True
        self.prev_text = "" 
        self.last_audio_time = time.time()

    async def push_audio(self, audio_bytes):
        """Receive raw PCM audio bytes (Int16) from WebSocket"""
        if self.running:
            # We keep Float32 for Silence Detection calculations
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            await self.queue.put(audio_data)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

    async def run(self):
        """Accumulate audio -> Detect Silence -> Send to Groq"""
        audio_buffer = []
        silence_timeout = 0.6  # Send if 0.6s silence detected
        
        while self.running:
            try:
                # Wait for data with timeout (to detect silence)
                chunk = await asyncio.wait_for(self.queue.get(), timeout=silence_timeout)
                
                if chunk is None: break
                audio_buffer.append(chunk)
                
                # If buffer gets too long (~6 seconds), force process to avoid huge lag
                if len(audio_buffer) >= 24: 
                    yield await self._transcribe_groq(audio_buffer)
                    audio_buffer = []
                    
            except asyncio.TimeoutError:
                # Silence Detected: User likely finished a sentence
                if len(audio_buffer) > 0:
                    yield await self._transcribe_groq(audio_buffer)
                    audio_buffer = [] 
            except Exception as e:
                print(f"STT Loop Error: {e}")
                break

    async def _transcribe_groq(self, audio_buffer):
        """Convert buffer to WAV and send to Groq API"""
        if not GROQ_AVAILABLE or not self.client:
            return None

        # 1. Prepare Audio Data (Float32 -> Int16)
        full_audio_float = np.concatenate(audio_buffer)
        
        # Simple energy check to ignore pure silence
        if np.abs(full_audio_float).mean() < 0.01:
            return None

        # Convert back to Int16 for WAV format
        full_audio_int16 = (full_audio_float * 32767).astype(np.int16)

        # 2. Write to In-Memory WAV File
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 2 bytes = 16-bit
            wav_file.setframerate(16000)
            wav_file.writeframes(full_audio_int16.tobytes())
        
        wav_io.seek(0) # Reset pointer to start of file
        wav_io.name = "audio.wav" # Groq requires a filename

        # 3. Call Groq API (Run in thread to be async-safe)
        try:
            transcription = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                file=(wav_io.name, wav_io.read()),
                model="whisper-large-v3", # Powerful model
                prompt=self.prev_text[-200:], # Give context
                response_format="json",
                language="en",
                temperature=0.0
            )
            
            text = transcription.text.strip()
            
            if text:
                self.prev_text += " " + text
                return {
                    "text": text,
                    "final": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            print(f"❌ Groq Whisper Error: {e}")
            return None