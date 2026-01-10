"""Test GPU fallback to CPU mode"""
import sys
sys.path.insert(0, 'piper1-gpl')

from livekit_piper_tts import TTS
import asyncio

async def test():
    print("Testing automatic GPU fallback...")
    print("Loading with GPU enabled...")
    
    tts = TTS(
        model_path='piper1-gpl/en_US-lessac-medium.onnx',
        use_cuda=True
    )
    print("✅ TTS loaded successfully")
    print("Attempting synthesis (will auto-fallback to CPU if GPU fails)...")
    
    try:
        stream = tts.synthesize('Hello world')
        async for chunk in stream:
            pass
        print("✅ Synthesis completed!")
        print(f"Final mode: {'GPU' if tts._use_cuda else 'CPU'}")
    except Exception as e:
        print(f"❌ Synthesis failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
