from livekit.plugins import silero
import asyncio

async def test_vad():
    try:
        vad = silero.VAD.load()
        print(f"Default VAD created: {vad}")
        if hasattr(vad, '_opts'):
            print(f"Default VAD options: {vad._opts}")
    except Exception as e:
        print(f"Error creating default VAD: {e}")

if __name__ == "__main__":
    asyncio.run(test_vad())
