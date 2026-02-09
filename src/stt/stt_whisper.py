import asyncio
import numpy as np
from datetime import datetime, timezone

# Global Model Cache
_GLOBAL_WHISPER_MODEL = None

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("Warning: faster-whisper not installed.")

class StreamingSTT:
    """
    Async Speech-to-Text for WebSocket Streams
    """
    def __init__(self, model_size="distil-small.en", device="cpu", compute_type="int8"):
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("faster-whisper is required for server-side processing")
        
        global _GLOBAL_WHISPER_MODEL
        
        # Load model only if it hasn't been loaded yet
        if _GLOBAL_WHISPER_MODEL is None:
            print(f"⏳ Loading Whisper Model ({model_size})... This happens only once.")
            _GLOBAL_WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
            print("✓ Model Loaded & Cached")
        
        # Use the cached model
        self.model = _GLOBAL_WHISPER_MODEL

        # Async Queue to hold audio chunks
        self.queue = asyncio.Queue()
        self.running = True
        self.prev_text = "" 

    async def push_audio(self, audio_bytes):
        """Receive raw PCM audio bytes from WebSocket"""
        if self.running:
            # Convert raw 16-bit PCM bytes to Float32 for Whisper
            # Vital: Must match the format sent by caller.html (Int16)
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            await self.queue.put(audio_data)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

    async def run(self):
        """Continuous transcription loop"""
        current_buffer = []
        
        while self.running:
            chunk = await self.queue.get()
            if chunk is None: break
            
            current_buffer.append(chunk)
            
            # Process every ~1 second (Assuming 16kHz audio)
            # Buffer length check: 16000 samples = 1 second. 
            # If chunks are small, wait for enough data.
            total_samples = sum(len(c) for c in current_buffer)
            
            if total_samples >= 16000: # Process every 1 second of audio
                full_audio = np.concatenate(current_buffer)
                
                # Run Inference in a thread so it doesn't block the WebSocket loop
                segments, _ = await asyncio.to_thread(
                    self.model.transcribe,
                    full_audio,
                    beam_size=5,
                    vad_filter=True,
                    initial_prompt=self.prev_text[-100:] 
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
                
                # Keep last 0.2s for overlap to avoid cutting words
                # 16000 * 0.2 = 3200 samples
                current_buffer = [full_audio[-3200:]] if len(full_audio) > 3200 else []