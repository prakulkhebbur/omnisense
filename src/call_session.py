import asyncio
from stt_whisper import StreamingSTT

class CallSession:
    def __init__(self, call_id, model_size="small.en"):
        self.call_id = call_id
        # Initialize Whisper instead of Vosk
        self.stt = StreamingSTT(model_size=model_size)

    async def start(self):
        asyncio.create_task(self._consume_transcripts())
        print(f"[{self.call_id}] Whisper STT Session Started")

    async def _consume_transcripts(self):
        async for result in self.stt.run():
            status = "FINAL" if result["final"] else "PARTIAL"
            print(f"[{self.call_id}] {status}: {result['text']}")

    async def send_audio(self, audio_bytes):
        await self.stt.push_audio(audio_bytes)

    async def end(self):
        await self.stt.stop()
        print(f"[{self.call_id}] Session Ended")