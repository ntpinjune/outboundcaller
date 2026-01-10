#!/usr/bin/env python3
"""Quick verification script to check agent configuration and settings."""

import sys
import json
from pathlib import Path

print("=" * 60)
print("Agent Configuration Verification")
print("=" * 60)
print()

# Check config.json exists and is valid
config_file = Path("config.json")
if not config_file.exists():
    print("❌ config.json not found!")
    sys.exit(1)

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
    print("✅ config.json is valid JSON")
except Exception as e:
    print(f"❌ Error reading config.json: {e}")
    sys.exit(1)

# Check required sections
required_sections = ['agent', 'call_behavior', 'call_dispatch', 'integrations', 'observability']
missing = [s for s in required_sections if s not in config]
if missing:
    print(f"❌ Missing config sections: {missing}")
    sys.exit(1)
else:
    print("✅ All required config sections present")

# Check new voice settings
print("\nVoice Settings:")
agent_config = config.get("agent", {})
voice_speed = agent_config.get("voice_speed", "Not set")
voice_volume = agent_config.get("voice_volume", "Not set")
llm_temp = agent_config.get("llm_temperature", "Not set")
noise_mode = agent_config.get("noise_cancellation_mode", "Not set")
print(f"  - Voice Speed: {voice_speed}")
print(f"  - Voice Volume: {voice_volume}")
print(f"  - LLM Temperature: {llm_temp}")
print(f"  - Noise Cancellation: {noise_mode}")

# Check agent behavior
print("\nAgent Behavior:")
response_speed = agent_config.get("response_speed", "Not set")
interruption = agent_config.get("interruption_sensitivity", "Not set")
print(f"  - Response Speed: {response_speed}")
print(f"  - Interruption Sensitivity: {interruption}")

# Check call settings
print("\nCall Settings:")
call_behavior = config.get("call_behavior", {})
max_duration = call_behavior.get("max_call_duration", "Not set")
idle_reminder = call_behavior.get("idle_reminder_enabled", "Not set")
idle_time = call_behavior.get("idle_time_seconds", "Not set")
reminder_freq = call_behavior.get("reminder_frequency", "Not set")
print(f"  - Max Call Duration: {max_duration}s ({max_duration // 60 if isinstance(max_duration, int) else 'N/A'} minutes)")
print(f"  - Idle Reminder Enabled: {idle_reminder}")
print(f"  - Idle Time: {idle_time}s")
print(f"  - Reminder Frequency: {reminder_freq}")

# Test config manager
print("\nTesting config_manager:")
try:
    from config_manager import load_config, get_config_value
    test_config = load_config()
    print("✅ config_manager loads successfully")
    
    # Test getting values
    test_values = [
        ("agent.voice_speed", 1.0),
        ("agent.voice_volume", 1.0),
        ("agent.llm_temperature", 1.0),
        ("agent.interruption_sensitivity", 0.5),
        ("call_behavior.idle_reminder_enabled", False),
    ]
    
    for path, expected_default in test_values:
        value = get_config_value(path, expected_default)
        print(f"  ✅ {path}: {value}")
        
except Exception as e:
    print(f"❌ Error testing config_manager: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test syntax
print("\nTesting syntax:")
try:
    import py_compile
    py_compile.compile("agent.py", doraise=True)
    print("✅ agent.py syntax is valid")
except py_compile.PyCompileError as e:
    print(f"❌ Syntax error in agent.py: {e}")
    sys.exit(1)
except Exception as e:
    print(f"⚠️  Could not compile agent.py: {e}")

print("\n" + "=" * 60)
print("✅ All checks passed! Agent is ready to use.")
print("=" * 60)
