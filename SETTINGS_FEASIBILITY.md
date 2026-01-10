# Settings Feasibility Analysis

This document analyzes which settings from the UI images can be implemented with your current TTS setup and LiveKit Agents SDK.

## Voice Settings Tab

### ✅ **Voice Speed** - SUPPORTED
- **TTS Support:** Piper TTS fully supports `speed` parameter (0.5-2.0)
- **Current:** Already in config (`tts_speed`)
- **Implementation:** Already working! Just needs UI slider (you have it)

### ✅ **Voice Volume** - SUPPORTED  
- **TTS Support:** Piper TTS fully supports `volume` parameter (0.0-1.0)
- **Current:** Already in config (`piper_volume`)
- **Implementation:** Already working! Just needs UI slider (you have it)

### ❌ **Voice Temperature** - NOT APPLICABLE TO TTS
- **Issue:** TTS doesn't have "temperature" - this is an LLM concept
- **Confusion:** The UI might be mislabeling LLM temperature as "Voice Temperature"
- **Solution:** 
  - This should be "LLM Temperature" in Agent Behavior tab
  - OR remove from Voice Settings (TTS can't control this)
- **Note:** LLM temperature controls response creativity, not voice characteristics

### ⚠️ **Background Sound** - POSSIBLE BUT NOT TTS
- **TTS Support:** Piper TTS cannot add background sounds
- **Solution:** Would need audio mixing layer (LiveKit audio processing)
- **Implementation:** 
  - Mix background audio track with TTS output
  - Requires custom audio processing (not trivial)
  - Better handled at LiveKit room level or frontend

### ✅ **Noise Cancellation Mode** - SUPPORTED
- **LiveKit Support:** Already using `BVCTelephony()` (Background Voice Cancellation)
- **Current:** Already implemented in agent code
- **Available Modes:**
  - `noise_cancellation.BVC()` - Background Voice Cancellation
  - `noise_cancellation.BVCTelephony()` - For telephony (currently using)
  - `noise_cancellation.NC()` - Standard Noise Cancellation
- **Implementation:** Already working! Just needs UI toggle

---

## Agent Behavior Tab

### ✅ **Response Speed** - SUPPORTED (via endpointing)
- **Current:** Already have `min_endpointing_delay` and `max_endpointing_delay`
- **How it works:** Controls how quickly agent responds after user stops speaking
- **Implementation:** Map to existing config values
- **Note:** Different from TTS speed (this is conversational timing, not speech rate)

### ✅ **Interruption Sensitivity** - SUPPORTED
- **LiveKit Support:** AgentSession has interruption parameters
- **Available Settings:**
  - `allow_interruptions` (bool) - Enable/disable interruptions
  - `min_interruption_duration` (float) - Min speech duration before interrupt (default: 0.5s)
  - `min_interruption_words` (int) - Min words before interrupt (default: 0)
- **Implementation:** Add to AgentSession constructor
- **Slider 0.0-1.0:** Map to `min_interruption_duration` (0.0 = 0.0s, 1.0 = 2.0s)

### ✅ **LLM Temperature** - SUPPORTED
- **LiveKit Support:** Can pass via `ModelSettings` in `llm_node`
- **Range:** Typically 0.0-2.0 (0.0 = deterministic, 2.0 = creative)
- **Implementation:** 
  - Store in config: `agent.llm_temperature` (default: 1.0)
  - Pass to LLM via ModelSettings in llm_node
- **Note:** This is what "Voice Temperature" in Voice Settings probably should be!

### ❌ **Enable Backchanneling** - NOT DIRECTLY SUPPORTED
- **LiveKit Support:** No built-in backchanneling feature
- **What it is:** Agent saying "uh-huh", "yeah", "right" during user speech
- **Implementation:** Would need custom logic:
  - Detect user speech segments
  - Inject backchannel words at intervals
  - Requires custom TTS synthesis at specific times
  - Complex to implement correctly

### ❌ **Backchannel Frequency** - NEEDS CUSTOM IMPLEMENTATION
- **Depends on:** Backchanneling feature being implemented
- **Implementation:** Custom logic to control how often to inject backchannel words

### ❌ **Backchannel Word List** - NEEDS CUSTOM IMPLEMENTATION
- **Depends on:** Backchanneling feature being implemented
- **Implementation:** Store list of words, randomly select during user speech

---

## Call Settings Tab

### ✅ **Maximum Call Time** - SUPPORTED
- **Current:** Already have `max_call_duration` (in seconds)
- **Implementation:** Already working! Just convert to minutes in UI

### ⚠️ **Idle Time and Reminder Frequency** - NEEDS CUSTOM IMPLEMENTATION
- **What it does:** After X seconds of silence, remind user (e.g., "Hello? Are you there?")
- **Current:** No built-in feature for this
- **Implementation:** Would need:
  - Monitor silence duration during conversation
  - Trigger reminder TTS after threshold
  - Repeat reminder X times if no response
  - Already have `initial_silence_wait` for greeting, but not for mid-call reminders
- **Complexity:** Medium - requires custom silence monitoring logic

---

## Summary: What's Possible

### ✅ **Fully Supported (Just Add UI):**
1. ✅ Voice Speed (TTS)
2. ✅ Voice Volume (TTS)
3. ✅ Noise Cancellation Mode (LiveKit)
4. ✅ Response Speed (endpointing delays)
5. ✅ Interruption Sensitivity (AgentSession)
6. ✅ LLM Temperature (ModelSettings)
7. ✅ Maximum Call Time (already have)

### ⚠️ **Possible but Needs Implementation:**
1. ⚠️ Background Sound (audio mixing - complex)
2. ⚠️ Idle Time and Reminder (custom silence monitoring)

### ❌ **Not Directly Supported (Would Need Custom Development):**
1. ❌ Backchanneling (complex custom logic)
2. ❌ Backchannel Frequency (depends on backchanneling)
3. ❌ Backchannel Word List (depends on backchanneling)

### ❌ **Not Applicable:**
1. ❌ Voice Temperature (TTS doesn't have this - it's LLM temperature)

---

## Recommended Implementation Plan

### Phase 1: Easy Wins (Already Supported)
1. ✅ Add Voice Speed slider (already in config)
2. ✅ Add Voice Volume slider (already in config)
3. ✅ Add Noise Cancellation dropdown (already implemented)
4. ✅ Add Response Speed controls (map to endpointing delays)
5. ✅ Add Interruption Sensitivity slider (add to AgentSession)
6. ✅ Add LLM Temperature slider (add to llm_node)
7. ✅ Convert Max Call Time to minutes (already have seconds)

### Phase 2: Medium Complexity
1. ⚠️ Add Idle Time and Reminder (custom silence monitoring)

### Phase 3: Advanced (If Needed)
1. ❌ Background Sound mixing
2. ❌ Backchanneling system

---

## Implementation Details

### Already Working Settings

```javascript
// Voice Speed (TTS)
tts_speed: 1.0-2.0  // Already in config

// Voice Volume (TTS)  
piper_volume: 0.0-1.0  // Already in config

// Max Call Duration
max_call_duration: 300  // Already in config (seconds)
```

### Settings That Need Code Changes

#### 1. Noise Cancellation Mode
```python
# In agent.py, modify room_input_options:
from livekit.plugins import noise_cancellation

# Get from config
noise_cancel_mode = get_config_value("agent.noise_cancellation_mode", "bvc_telephony")

if noise_cancel_mode == "bvc":
    nc = noise_cancellation.BVC()
elif noise_cancel_mode == "bvc_telephony":
    nc = noise_cancellation.BVCTelephony()
elif noise_cancel_mode == "nc":
    nc = noise_cancellation.NC()
else:
    nc = None  # Disabled

room_input_options = RoomInputOptions(
    noise_cancellation=nc,
)
```

#### 2. Interruption Sensitivity
```python
# In AgentSession constructor:
min_interruption_duration = float(get_config_value("agent.min_interruption_duration", "0.5"))
min_interruption_words = int(get_config_value("agent.min_interruption_words", "0"))
allow_interruptions = get_config_value("agent.allow_interruptions", True)

session = AgentSession(
    # ... other params ...
    allow_interruptions=allow_interruptions,
    min_interruption_duration=min_interruption_duration,
    min_interruption_words=min_interruption_words,
)
```

#### 3. LLM Temperature
```python
# In llm_node method:
from livekit.agents import ModelSettings

llm_temperature = float(get_config_value("agent.llm_temperature", "1.0"))

model_settings = ModelSettings(
    temperature=llm_temperature,
    # ... other settings ...
)

async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
    yield chunk
```

#### 4. Response Speed (via endpointing delays)
```python
# Already have these, just need better mapping in UI:
min_endpointing_delay = float(get_config_value("call_behavior.min_endpointing_delay", "0.5"))
max_endpointing_delay = float(get_config_value("call_behavior.max_endpointing_delay", "15.0"))

# Could add "response_speed" preset:
# Fast: min=0.2, max=3.0
# Normal: min=0.5, max=15.0 (current)
# Moderate: min=1.0, max=20.0
```

---

## What TTS Can and Cannot Do

### ✅ **TTS Can Control:**
- Speech speed (how fast words are spoken)
- Volume (audio level)
- Voice characteristics (via model selection)
- Speaking variation (noise_scale, noise_w)

### ❌ **TTS Cannot Control:**
- Response timing (this is agent-level, not TTS)
- Interruption handling (this is agent-level)
- Conversation flow (this is LLM-level)
- Temperature (this is LLM-level)
- Background sounds (this is audio mixing)
- Reminders (this is agent logic)

---

## Conclusion

**Most settings are possible!** About 70% are directly supported or easy to add:

- ✅ **7 out of 10 settings** can be implemented with minimal code changes
- ⚠️ **2 settings** need custom implementation (but feasible)
- ❌ **1 setting** (Backchanneling) is complex and may not be worth it

**Recommendation:** Start with Phase 1 (Easy Wins) - these give you most of the functionality with minimal effort!
