import asyncio
from stt_whisper import StreamingSTT

class CallSession:
    def __init__(self, call_id, model_size="distil-large-v3"):
        self.call_id = call_id
        self.stt = StreamingSTT(model_size=model_size)

    async def start(self):
        asyncio.create_task(self._consume_transcripts())
        print(f"[{self.call_id}] distil-large-v3 session active")

    async def _consume_transcripts(self):
        async for result in self.stt.run():
            print(f"[{self.call_id}] {result['text']}")

    async def send_audio(self, audio_bytes):
        await self.stt.push_audio(audio_bytes)

    async def end(self):
        await self.stt.stop()
        print(f"[{self.call_id}] session closed")