import asyncio
import sounddevice as sd
from call_session import CallSession

# Whisper requires exactly 16000Hz
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000 # ~250ms

async def test_call(call_id, duration=30):
    call = CallSession(call_id, model_size="distil-large-v3")
    await call.start()

    loop = asyncio.get_running_loop()

    def callback(indata, frames, time, status):
        if status:
            print(f"Error: {status}")
        
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(call.send_audio(bytes(indata)))
        )

    print("--- Recording with distil-large-v3 (Speak now) ---")
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
    # Disable the symlink warning if it appears
    import os
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    
    asyncio.run(test_call("DISTIL_V3_TEST"))