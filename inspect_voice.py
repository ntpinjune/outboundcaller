try:
    import livekit.agents.voice
    print("voice module exists")
    print(dir(livekit.agents.voice))
except ImportError as e:
    print(f"voice module import failed: {e}")
