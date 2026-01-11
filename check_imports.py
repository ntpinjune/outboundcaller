try:
    from livekit.agents.pipeline import VoicePipelineAgent
    print("VoicePipelineAgent found in livekit.agents.pipeline")
except ImportError:
    try:
        from livekit.agents import VoicePipelineAgent
        print("VoicePipelineAgent found in livekit.agents")
    except ImportError:
        print("VoicePipelineAgent NOT found")

try:
    from livekit.agents import AgentSession
    print("AgentSession found")
except ImportError:
    print("AgentSession NOT found")
