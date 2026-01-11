from livekit.agents import AgentSession
import inspect

try:
    sig = inspect.signature(AgentSession.__init__)
    # print(f"AgentSession.__init__ signature: {sig}")
    if 'vad' in sig.parameters:
        print("vad parameter FOUND")
        print(sig.parameters['vad'])
    else:
        print("vad parameter NOT found")
except Exception as e:
    print(f"Error inspecting signature: {e}")
