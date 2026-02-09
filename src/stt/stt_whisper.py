import asyncio
import numpy as np
import time
from datetime import datetime, timezone

# Try importing Faster Whisper (Recommended for server-side)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("Warning: faster-whisper not installed. Install with: pip install faster-whisper")

class StreamingSTT:
    """
    Async Speech-to-Text for WebSocket Streams
    """
    def __init__(self, model_size="distil-small.en", device="cpu", compute_type="int8"):
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("faster-whisper is required for server-side processing")

        print(f"Loading Whisper Model: {model_size}...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("✓ Model Loaded")

        # Async Queue to hold audio chunks from WebSocket
        self.queue = asyncio.Queue()
        self.running = True
        
        # Buffer for context
        self.audio_buffer = [] 
        self.prev_text = "" 

    async def push_audio(self, audio_bytes):
        """Receive raw PCM audio bytes from WebSocket"""
        if self.running:
            # Convert raw 16-bit PCM bytes to Float32 for Whisper
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            await self.queue.put(audio_data)

    async def stop(self):
        self.running = False
        await self.queue.put(None)  # Signal to stop

    async def run(self):
        """Continuous transcription loop"""
        current_buffer = []
        
        while self.running:
            # Wait for audio chunks
            chunk = await self.queue.get()
            if chunk is None: break
            
            current_buffer.append(chunk)
            
            # Process every ~1 second of audio (assuming 4 chunks/sec from client)
            # Adjust this length based on how often you want updates
            if len(current_buffer) >= 5: 
                full_audio = np.concatenate(current_buffer)
                
                # Run Inference (run in thread to not block asyncio loop)
                segments, _ = await asyncio.to_thread(
                    self.model.transcribe,
                    full_audio,
                    beam_size=5,
                    vad_filter=True, # Filter silence
                    initial_prompt=self.prev_text[-100:] # Provide context
                )
                
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        self.prev_text += " " + text
                        yield {
                            "text": text,
                            "final": True,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                
                # Keep last 0.5s for overlap context
                current_buffer = current_buffer[-2:]