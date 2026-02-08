import asyncio
import sounddevice as sd
from call_session import CallSession

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000 # ~250ms per chunk for low latency

async def test_call(call_id, duration=30):
    # Using 'small.en' for high accuracy on CPU
    call = CallSession(call_id, model_size="small.en")
    await call.start()

    loop = asyncio.get_running_loop()

    def callback(indata, frames, time, status):
        if status:
            print(status)
        # Offload audio processing to the queue
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(call.send_audio(bytes(indata)))
        )

    print("--- Recording Started (Speak now) ---")
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        await asyncio.sleep(duration)

    await call.end()

if __name__ == "__main__":
    asyncio.run(test_call("CALL_WHISPER_001"))