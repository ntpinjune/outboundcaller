import livekit.agents
print(dir(livekit.agents))
try:
    import livekit.agents.pipeline
    print("pipeline module exists")
    print(dir(livekit.agents.pipeline))
except ImportError as e:
    print(f"pipeline module import failed: {e}")
