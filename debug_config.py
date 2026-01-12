import os
import sys
import json
# Make sure we can import from the current directory
sys.path.append(os.getcwd())

try:
    from config_manager import get_config_value, load_config
    print("✅ config_manager imported successfully")
except ImportError as e:
    print(f"❌ Failed to import config_manager: {e}")
    sys.exit(1)

# 1. Check Config Value
print("\n--- Checking Config Values ---")
config = load_config()
agent_config = config.get("agent", {})
tts_provider_config = agent_config.get("tts_provider")
print(f"config.json 'tts_provider': '{tts_provider_config}'")

resolved_tts = get_config_value("agent.tts_provider")
print(f"get_config_value('agent.tts_provider'): '{resolved_tts}'")

# 2. Check Environment Variable
print("\n--- Checking Environment Variables ---")
env_tts = os.getenv("TTS_PROVIDER")
print(f"os.getenv('TTS_PROVIDER'): '{env_tts}'")

# 3. Check OpenAI Plugin Availability
print("\n--- Checking OpenAI Plugin ---")
try:
    import livekit.plugins.openai
    print("✅ livekit.plugins.openai imported successfully")
except ImportError as e:
    print(f"❌ livekit.plugins.openai NOT found: {e}")

try:
    from livekit.plugins.openai import TTS as OpenAITTS
    print("✅ livekit.plugins.openai.TTS imported successfully")
except ImportError as e:
    print(f"❌ livekit.plugins.openai.TTS NOT found: {e}")

# 4. Check Current Defaults logic simulation
print("\n--- Checking Agent Logic Simulation ---")
OPENAI_TTS_AVAILABLE = False
try:
    from livekit.plugins.openai import TTS as OpenAITTS
    OPENAI_TTS_AVAILABLE = True
except ImportError:
    pass

print(f"OPENAI_TTS_AVAILABLE: {OPENAI_TTS_AVAILABLE}")

resolved_provider = str(resolved_tts).lower() if resolved_tts else ""
print(f"Resolved Provider (lower): '{resolved_provider}'")

if resolved_provider == "openai":
    if OPENAI_TTS_AVAILABLE:
        print("✅ Simulation: Config says 'openai' and plugin is available. Should work.")
    else:
        print("⚠️  Simulation: Config says 'openai' but plugin missing. Agent will fallback.")
else:
    print(f"ℹ️  Simulation: Config is set to '{resolved_provider}'. Agent will try to use that.")
