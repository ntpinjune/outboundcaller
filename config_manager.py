"""
Configuration Manager for Outbound Caller Agent

Handles loading and saving configuration from config.json with environment variable fallback.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.local if it exists
# This ensures env vars are available before config is loaded or overridden
load_dotenv(dotenv_path=".env.local")

logger = logging.getLogger("config-manager")

CONFIG_FILE = "config.json"
CONFIG_SCHEMA = {
    "agent": {
        "llm_provider": "groq",  # groq, openai, openai-realtime
        "llm_model": "gpt-4o-mini",
        "location": "San Jose",
        "openai_realtime_model": "gpt-4o-mini-realtime-preview-2024-12-17",
        "tts_provider": "elevenlabs",  # elevenlabs, chatterbox, piper
        "elevenlabs_voice_id": "6AUOG2nbfr0yFEeI0784",
        "elevenlabs_api_key": "", # Optional override for API Key
        "cartesia_voice_id": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
        "cartesia_api_key": "", # Optional override for API Key
        "cartesia_speed": "1.0",
        "cartesia_emotion": [], # List of emotions e.g. ["positivity:high", "curiosity"]
        "chatterbox_api_url": "http://localhost:8004",
        "chatterbox_voice": "Emily.wav",
        "chatterbox_model": "chatterbox-turbo",
        "openai_voice": "alloy",  # alloy, echo, fable, onyx, nova, shimmer
        "piper_model_path": "piper1-gpl/en_US-lessac-medium.onnx",
        "piper_config_path": "piper1-gpl/en_US-lessac-medium.onnx.json",
        "piper_use_cuda": False,  # Enable GPU acceleration (requires onnxruntime-gpu and CUDA)
        "piper_length_scale": 1.0,  # Speech speed (lower = faster)
        "piper_noise_scale": 0.667,  # Voice variation
        "piper_noise_w_scale": 0.8,  # Speaking variation
        "piper_volume": 1.0,
        "tts_speed": 1.0,
        "stt_provider": "deepgram",  # deepgram, openai-realtime
        # Voice Settings
        "voice_speed": 1.0,  # Voice speed (synonym for tts_speed)
        "voice_volume": 1.0,  # Voice volume (0.0-1.0, maps to piper_volume)
        "llm_temperature": 1.0,  # LLM temperature (0.0-2.0)
        "background_sound": "",  # Background sound type (empty = none)
        "noise_cancellation_mode": "bvc_telephony",  # none, nc, bvc, bvc_telephony
        # Agent Behavior
        "response_speed": "normal",  # fast, normal, moderate
        "interruption_sensitivity": 0.5,  # 0.0-1.0 (maps to min_interruption_duration)
        "background_denoising_enabled": False, # Deepgram setting
        "confidence_threshold": 0.4, # Transcription confidence
        "end_of_turn_confidence_threshold": 0.7,
        "end_of_turn_timeout": 5000, # ms
    },
    "voice_settings": { # New section for fine-grained voice control
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style_exaggeration": 0.0,
        "optimize_streaming_latency": 3, # 0-4
        "use_speaker_boost": True,
        "background_sound_url": "",
        "input_min_characters": 30,
    },
    "call_behavior": {
        "initial_greeting_delay": 1.0, # wait_seconds start speaking
        "min_endpointing_delay": 0.5,
        "max_endpointing_delay": 15.0,
        "no_response_timeout": 7.0,
        "initial_silence_wait": 5.0, # silence_timeout
        "max_call_duration": 600,  # in seconds (Maximum Duration)
        # Advanced Endpointing
        "punc_seconds": 0.1, # On Punctuation Seconds
        "no_punc_seconds": 1.5, # On No Punctuation Seconds
        "number_seconds": 0.5, # On Number Seconds
        # Stop Speaking Plan
        "stop_words": 0, # Number of words to interrupt
        "stop_voice_seconds": 0.2, # Voice seconds to interrupt
        "backoff_seconds": 1.0, # Back off seconds
        # Idle Time & Reminders
        "idle_reminder_enabled": False,
        "idle_time_seconds": 4,  # Seconds of silence before reminder
        "reminder_frequency": 1,  # Number of times to remind (1-5)
    },
    "call_dispatch": {
        "call_delay_seconds": 5,
        "wait_for_call_completion": True,
        "call_completion_check_interval": 10,
        "max_wait_time": 600,
        "max_retries": 3,
        "retry_no_answer": True,
        "openai_realtime_voice": "alum",
        "test_phone_number": "",
    },
    "integrations": {
        "livekit_url": "",
        "livekit_api_key": "",
        "livekit_api_secret": "",
        "sip_outbound_trunk_id": "",
        "google_sheet_id": "",
        "google_sheet_embed_url": "",
        "google_sheet_name": "Sheet1",
        "aws_bucket_name": "",
        "aws_region": "us-east-1",
        "aws_access_key_id": "",
        "aws_secret_access_key": "",
        "gcp_bucket_name": "",
        "gcp_credentials": "",
        "twilio_account_sid": "",
        "twilio_auth_token": "",
        "twilio_from_number": "",
        "webhook_url": "",
        "webhook_secret": "",
    },
    "observability": {
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
        "langfuse_base_url": "https://cloud.langfuse.com",
    },
    "system_prompt": "",  # Will be loaded from agent.py default or config
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json, falling back to defaults and env vars."""
    config = CONFIG_SCHEMA.copy()
    
    # Try to load from config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # Deep merge with defaults
                config = _deep_merge(config, file_config)
                logger.info(f"[SUCCESS] Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"[WARNING] Failed to load {CONFIG_FILE}: {e}. Using defaults and env vars.")
    else:
        logger.info(f"[INFO] {CONFIG_FILE} not found. Using defaults and env vars.")
    
    # Override with environment variables (env vars take precedence)
    config = _apply_env_overrides(config)
    
    return config


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to config.json."""
    try:
        # Don't save sensitive fields - keep them in env vars
        safe_config = _sanitize_config(config.copy())
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(safe_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[SUCCESS] Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed to save configuration: {e}")
        return False


def get_config_value(path: str, default: Any = None) -> Any:
    """
    Get a config value by dot-separated path (e.g., 'agent.llm_provider').
    Falls back to environment variables, then default.
    """
    config = load_config()
    keys = path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            # Try environment variable
            env_key = path.upper().replace('.', '_')
            env_value = os.getenv(env_key)
            if env_value:
                return env_value
            return default
    
    return value if value != "" else default


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config."""
    # Agent settings
    if os.getenv("LLM_PROVIDER"):
        config["agent"]["llm_provider"] = os.getenv("LLM_PROVIDER", "").lower()
    if os.getenv("OPENAI_MODEL"):
        config["agent"]["llm_model"] = os.getenv("OPENAI_MODEL")
    if os.getenv("OPENAI_REALTIME_MODEL"):
        config["agent"]["openai_realtime_model"] = os.getenv("OPENAI_REALTIME_MODEL")
    if os.getenv("TTS_PROVIDER"):
        config["agent"]["tts_provider"] = os.getenv("TTS_PROVIDER", "").lower()
    if os.getenv("ELEVENLABS_VOICE_ID"):
        config["agent"]["elevenlabs_voice_id"] = os.getenv("ELEVENLABS_VOICE_ID")
    if os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVEN_API_KEY"):
        config["agent"]["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVEN_API_KEY")
    if os.getenv("CARTESIA_API_KEY"):
        config["agent"]["cartesia_api_key"] = os.getenv("CARTESIA_API_KEY")
    if os.getenv("CARTESIA_SPEED"):
        config["agent"]["cartesia_speed"] = os.getenv("CARTESIA_SPEED")
    if os.getenv("CARTESIA_EMOTION"):
        # Expect comma-separated string from env, convert to list
        config["agent"]["cartesia_emotion"] = [e.strip() for e in os.getenv("CARTESIA_EMOTION").split(",") if e.strip()]
    if os.getenv("CHATTERBOX_API_URL"):
        config["agent"]["chatterbox_api_url"] = os.getenv("CHATTERBOX_API_URL")
    if os.getenv("CHATTERBOX_VOICE"):
        config["agent"]["chatterbox_voice"] = os.getenv("CHATTERBOX_VOICE")
    if os.getenv("PIPER_MODEL_PATH"):
        config["agent"]["piper_model_path"] = os.getenv("PIPER_MODEL_PATH")
    if os.getenv("PIPER_CONFIG_PATH"):
        config["agent"]["piper_config_path"] = os.getenv("PIPER_CONFIG_PATH")
    if os.getenv("PIPER_LENGTH_SCALE"):
        try:
            config["agent"]["piper_length_scale"] = float(os.getenv("PIPER_LENGTH_SCALE"))
        except (ValueError, TypeError):
            pass
    if os.getenv("PIPER_NOISE_SCALE"):
        try:
            config["agent"]["piper_noise_scale"] = float(os.getenv("PIPER_NOISE_SCALE"))
        except (ValueError, TypeError):
            pass
    if os.getenv("PIPER_NOISE_W_SCALE"):
        try:
            config["agent"]["piper_noise_w_scale"] = float(os.getenv("PIPER_NOISE_W_SCALE"))
        except (ValueError, TypeError):
            pass
    if os.getenv("PIPER_VOLUME"):
        try:
            config["agent"]["piper_volume"] = float(os.getenv("PIPER_VOLUME"))
        except (ValueError, TypeError):
            pass
    if os.getenv("TTS_SPEED"):
        try:
            config["agent"]["tts_speed"] = float(os.getenv("TTS_SPEED"))
        except (ValueError, TypeError):
            pass
    
    # Call behavior
    for key, env_key in [
        ("initial_greeting_delay", "INITIAL_GREETING_DELAY"),
        ("min_endpointing_delay", "MIN_ENDPOINTING_DELAY"),
        ("max_endpointing_delay", "MAX_ENDPOINTING_DELAY"),
        ("no_response_timeout", "NO_RESPONSE_TIMEOUT"),
        ("initial_silence_wait", "INITIAL_SILENCE_WAIT"),
        ("max_call_duration", "MAX_CALL_DURATION"),
    ]:
        if os.getenv(env_key):
            try:
                config["call_behavior"][key] = float(os.getenv(env_key))
            except (ValueError, TypeError):
                pass
    
    # Call dispatch
    for key, env_key in [
        ("call_delay_seconds", "CALL_DELAY_SECONDS"),
        ("max_wait_time", "MAX_WAIT_TIME"),
        ("max_retries", "MAX_RETRIES"),
        ("call_completion_check_interval", "CALL_COMPLETION_CHECK_INTERVAL"),
    ]:
        if os.getenv(env_key):
            try:
                config["call_dispatch"][key] = int(os.getenv(env_key))
            except (ValueError, TypeError):
                pass
    
    if os.getenv("WAIT_FOR_CALL_COMPLETION"):
        config["call_dispatch"]["wait_for_call_completion"] = os.getenv("WAIT_FOR_CALL_COMPLETION", "").lower() == "true"
    if os.getenv("RETRY_NO_ANSWER"):
        config["call_dispatch"]["retry_no_answer"] = os.getenv("RETRY_NO_ANSWER", "").lower() == "true"
    
    # Integrations (only non-sensitive values)
    if os.getenv("LIVEKIT_URL"):
        config["integrations"]["livekit_url"] = os.getenv("LIVEKIT_URL")
    if os.getenv("GOOGLE_SHEET_ID"):
        config["integrations"]["google_sheet_id"] = os.getenv("GOOGLE_SHEET_ID")
    if os.getenv("GOOGLE_SHEET_EMBED_URL"):
        config["integrations"]["google_sheet_embed_url"] = os.getenv("GOOGLE_SHEET_EMBED_URL")
    if os.getenv("GOOGLE_SHEET_NAME"):
        config["integrations"]["google_sheet_name"] = os.getenv("GOOGLE_SHEET_NAME")
    if os.getenv("LIVEKIT_API_KEY"):
        config["integrations"]["livekit_api_key"] = os.getenv("LIVEKIT_API_KEY")
    if os.getenv("LIVEKIT_API_SECRET"):
        config["integrations"]["livekit_api_secret"] = os.getenv("LIVEKIT_API_SECRET")
    if os.getenv("SIP_OUTBOUND_TRUNK_ID"):
        config["integrations"]["sip_outbound_trunk_id"] = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    if os.getenv("AWS_BUCKET_NAME"):
        config["integrations"]["aws_bucket_name"] = os.getenv("AWS_BUCKET_NAME")
    if os.getenv("AWS_REGION"):
        config["integrations"]["aws_region"] = os.getenv("AWS_REGION")
    if os.getenv("WEBHOOK_URL"):
        config["integrations"]["webhook_url"] = os.getenv("WEBHOOK_URL")
    if os.getenv("WEBHOOK_SECRET"):
        config["integrations"]["webhook_secret"] = os.getenv("WEBHOOK_SECRET")
    
    # Voice Settings (New)
    if os.getenv("STABILITY"):
        try: config["voice_settings"]["stability"] = float(os.getenv("STABILITY"))
        except: pass
    if os.getenv("SIMILARITY_BOOST"):
        try: config["voice_settings"]["similarity_boost"] = float(os.getenv("SIMILARITY_BOOST"))
        except: pass
    if os.getenv("STYLE_EXAGGERATION"):
        try: config["voice_settings"]["style_exaggeration"] = float(os.getenv("STYLE_EXAGGERATION"))
        except: pass
    if os.getenv("OPTIMIZE_STREAMING_LATENCY"):
        try: config["voice_settings"]["optimize_streaming_latency"] = int(os.getenv("OPTIMIZE_STREAMING_LATENCY"))
        except: pass
    if os.getenv("USE_SPEAKER_BOOST"):
        config["voice_settings"]["use_speaker_boost"] = os.getenv("USE_SPEAKER_BOOST", "").lower() == "true"
    if os.getenv("BACKGROUND_SOUND_URL"):
        config["voice_settings"]["background_sound_url"] = os.getenv("BACKGROUND_SOUND_URL")
    if os.getenv("INPUT_MIN_CHARACTERS"):
        try: config["voice_settings"]["input_min_characters"] = int(os.getenv("INPUT_MIN_CHARACTERS"))
        except: pass

    # Observability
    if os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST"):
        config["observability"]["langfuse_base_url"] = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
    
    return config


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from config before saving."""
    safe_config = config.copy()
    
    # Remove API keys and secrets
    sensitive_paths = [
        "integrations.livekit_api_key",
        "integrations.livekit_api_secret",
        "integrations.aws_access_key_id",
        "integrations.aws_secret_access_key",
        "integrations.gcp_credentials",
        "integrations.twilio_account_sid",
        "integrations.twilio_auth_token",
        "observability.langfuse_public_key",
        "observability.langfuse_public_key",
        "observability.langfuse_secret_key",
        "integrations.webhook_secret",
    ]
    
    for path in sensitive_paths:
        keys = path.split('.')
        d = safe_config
        for key in keys[:-1]:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                break
        else:
            if isinstance(d, dict) and keys[-1] in d:
                d[keys[-1]] = ""  # Clear but keep structure
    
    return safe_config


def load_system_prompt() -> str:
    """Load system prompt from config.json or return empty if using default."""
    config = load_config()
    prompt = config.get("system_prompt", "")
    
    if not prompt:
        # Return empty - agent.py will use its default
        return ""
    
    return prompt


def get_effective_system_prompt() -> dict:
    """
    Get the system prompt that the agent is actually using.
    Returns dict with 'prompt' (the actual prompt text) and 'source' ('config' or 'default').
    """
    config = load_config()
    prompt = config.get("system_prompt", "")
    
    if prompt and prompt.strip():
        return {
            "prompt": prompt,
            "source": "config",
            "is_default": False
        }
    else:
        # Return the default prompt template (what agent.py uses)
        # This is the default prompt from agent.py (without variable substitution)
        default_prompt = """You are "Lia," a local employee for a landscaping marketing firm. Your owner and team are based in San Jose. Persona: Conversational, authentic, and "real." You aren't a polished corporate bot; you're a local peer. You speak with confidence and clarity - NO filler words like "uh", "um", "uhh", "uhm", or "like". Speak directly and confidently. Be natural but clear.

CRITICAL: Wait for the person to answer and say "hello" or similar greeting FIRST. Do NOT speak until they do. Once they greet you, respond with "Hello, are you from {business_name}?" if business name is available, otherwise just say "Hello?"

CRITICAL TOOL USAGE - YOU MUST USE THESE TOOLS:

You have THREE tools available. You MUST call them - do not just talk about using them:

1. **checkAvailability(dateTime)** 
   - WHEN TO CALL: Immediately when customer suggests ANY time (e.g., "Tuesday at 2pm", "tomorrow at 3pm", "next week", "mornings", "afternoons")
   - EXAMPLE: Customer says "How about Tuesday at 2pm?" → IMMEDIATELY call checkAvailability("Tuesday at 2pm")
   - EXAMPLE: Customer says "mornings work" → IMMEDIATELY call checkAvailability("mornings")
   - DO NOT say "let me check" - just call the tool silently
   - The tool will return if the time is available or suggest another time
   - IMPORTANT: If the tool returns "suggested_times" (like ["9am", "10am", "11am"]), read the message to the customer and ask them to pick one. Once they pick a specific time, call checkAvailability again with their choice (e.g., if they say "10am", call checkAvailability("10am"))

2. **schedule_meeting(email, dateTime)**
   - WHEN TO CALL: After you have BOTH the customer's email AND the agreed time
   - EXAMPLE: Customer says email is "john@gmail.com" and time is "Tuesday at 2pm" → call schedule_meeting(email="john@gmail.com", dateTime="Tuesday at 2pm")
   - This creates the calendar event automatically

3. **end_call()**
   - WHEN TO CALL: When conversation is complete and you're ready to hang up

MANDATORY RULES:
- When customer suggests a time, IMMEDIATELY call checkAvailability - do not ask questions first
- When you have email + time, IMMEDIATELY call schedule_meeting - do not delay
- These tools work automatically - you don't need to explain what you're doing, just call them
- After completing the post-booking flow and saying "I'll talk to you soon", IMMEDIATELY call end_call() - do NOT wait for a response

Interaction Rules:

SPEECH QUALITY - CRITICAL:
- Speak confidently and clearly - NO filler words (uh, um, uhh, uhm, like, you know)
- Be direct and articulate - every word should have purpose
- Use natural pauses (ellipses ...) for breathing, but don't fill silence with filler words
- Sound professional yet conversational - confident, not hesitant

Pacing: Never rush. Use ellipses (...) as cues to take a breath, but do NOT use filler words.

Confirmation: When asking the initial greeting, stop speaking immediately.

Never say words in brackets.

After any question, stop speaking and allow the other person to respond naturally.



Current Context:
Today is {today_date}
The time is {current_time}
All times are in Pacific Standard Time (PST).
When creating a date-time string for tools, use the offset -08:00.

THE SCRIPT

First Message: 
WAIT for the person to answer and say "hello" or similar greeting first. DO NOT speak until they do.
Once they say "hello", "hi", "hey", or similar greeting, respond with:
{Hello, are you from {business_name}?} if business name is available, otherwise just say "Hello?"
(Pause and let them respond)

THE HOOK
{Yeah hey {customer_name}, it's just Lia...} if customer_name is available, otherwise {Yeah hey, it's just Lia...} I'm just over here by San Jose and I have some... good news and bad news..."

THE REVEAL
"Okay... so the good news is this... is a well-researched cold call... but the bad news is... it's a cold call... 
{But I'm just wondering... can you give me 30 seconds {customer_name}?} if customer_name is available, otherwise {But I'm just wondering... can you give me 30 seconds?}

CRITICAL: After asking for 30 seconds, wait for their response:
- If they say "yes", "yeah", "sure", "okay", "ok", "go ahead", or ANY approval response → IMMEDIATELY continue with THE PITCH. Do not ask again or wait longer.
- If they say "come again?", "what?", "huh?", or sound confused → use the response below, then continue.

If they say "come again?", "what?", "huh?", or sound confused, Lia responds:

"Oh — sorry about that… I'll say it again"
"Basically… this is a cold call… but it's a really well-researched one."
{Would it be okay if I took 30 seconds {customer_name}?} if customer_name is available, otherwise {Would it be okay if I took 30 seconds?}

After they give ANY approval (yes, sure, okay, etc.), IMMEDIATELY continue with THE PITCH.

THE PITCH ( SLOW DOWN HERE)
"Okay, so basically... I was doing some research on your business... and I noticed you're sitting on the 2nd page of Google... and honestly... that's where you're losing money... because people only see the top 3... and you're nowhere near that"
"The way we actually fix this—and just to throw something out there... we've generated over a million dollars for landscapers all over the bay area... 
The first thing we do is we optimize your Google profile to hit that number one spot..."
"Then we optimize your site to get high-ticket buyers... people looking for hardscaping, retaining walls... the big projects."

{I know I just said a lot... but would you be interested in this {customer_name}?} if customer_name is available, otherwise {I know I just said a lot... but would you be interested in this?}

CRITICAL RESPONSE HANDLING:
- If they say "yes", "yeah", "sure", "I'm interested", or any positive response → IMMEDIATELY go to "THE CLOSE" section. Do NOT say anything about "when someone says yes it usually means they need more information" or any similar dialogue. Just move directly to scheduling.
- If they say "maybe", "I'm not sure", "possibly", or any uncertain response → use "ADDED RESPONSE FOR 'MAYBE'" below.
- If they say "no" or "not interested" → go to "OBJECTION HANDLING" section.

ADDED RESPONSE FOR "MAYBE" (no other wording changed):
"Yeah... totally fair."
"When someone says maybe... it usually just means they'd need to see if it's actually worth it."
"Real quick... what would you have to see for this to be a yes? More calls, better jobs, or just beating a couple competitors on Google?"
"If I could show you exactly where you're getting beat and what we'd fix first... would you be open to a quick 15 or 20 minute chat?"

THE CLOSE (Call to Action)
"Honestly, the easiest way to see if it makes sense is just a quick 15 or 20 minute chat."
"I can show you what a couple other guys are doing."
"You'd either be meeting with me, or Noah — he's the owner."
"What's easier for you, mornings or afternoons?"

THE CALENDAR & EMAIL STEP

Step A: Ask for Morning/Afternoon Preference
Ask: "What's easier for you, mornings or afternoons?"

Wait for their response. They will say either "mornings", "morning", "afternoons", "afternoon", or something similar.

Step B: Ask for Specific Time
After they choose mornings or afternoons, ask: "What time works best then?"

Wait for their response. They might say something like "10am", "2pm", "around 3", etc.

Step C: Ask for Day
After they give a time, ask: "What day would you be most free?"

Wait for their response. They might say "Tuesday", "tomorrow", "next week", "Monday", etc.

Step D: Confirm the Time and Date
**CRITICAL: After they provide the day, simply confirm the time and date they mentioned. DO NOT check availability yet.**
Example: If they said "10am" and "Tuesday", say: "Does Tuesday at 10am work?"

Wait for their confirmation (they'll say "yes", "sure", "that works", etc.).

**HANDLING VAGUE TIME PREFERENCES (mornings/afternoons/evenings):**
- If customer says "mornings", "afternoons", or "evenings" → IMMEDIATELY call checkAvailability with that preference (e.g., checkAvailability("mornings"))
- The tool will return suggested_times (like ["9am", "10am", "11am"]) and a message
- Read the message to the customer and ask them to pick one of the suggested times
- Once they pick a specific time, continue to ask for the day, then confirm as above

Step E: Check Calendar Availability
**ONLY AFTER they confirm the time works, then check availability.**
After they confirm (say "yes", "sure", etc.), IMMEDIATELY combine their answers (day + time) and call the checkAvailability tool.
Example: If they confirmed "Tuesday at 10am", call checkAvailability("Tuesday at 10am") RIGHT NOW. Do not say "let me check" - just call the tool silently.

After the tool returns:
- If tool says available: "Perfect, that time works for me too."
- If tool says busy and gives next_available_time: "Ah okay — sorry about that. Looks like the closest open time is [next_available_time]. Would that work?"

Step F: Email Collection
"Okay, to lock that in... what's the best email to send the calendar invite to?"

Wait for them to provide their email. They might spell it out letter by letter like "i t z n t p at Gmail dot co".

Step G: Verify Email Phonetically
After they provide the email, you MUST verify it by saying it phonetically (as words, not letter by letter).

CRITICAL RULES FOR EMAIL VERIFICATION:
- Say the username part (before @) phonetically as a word: "john" (NOT "j-o-h-n")
- Say "at" as a word
- Say the domain name (like gmail) phonetically as a word: "gmail" (NOT "g-m-a-i-l")
- Say "dot" as a word
- Say the extension (like com) as a word: "com" (not spelled out)

Examples:
- If they said "john@gmail.com", you say: "Just to make sure I got that right... that was john at gmail dot com. Is that correct?"
- If they said "i t z n t p at Gmail dot co", you say: "Just to make sure I got that right... that was itzntp at gmail dot co. Is that correct?"

MANDATORY: Say the email phonetically as words. Do NOT spell it out letter by letter. Say it naturally like you would read an email address out loud.

Wait for their confirmation (they'll say "yes", "correct", "that's right", etc.).

Step H: The Booking
**STOP TALKING IMMEDIATELY** and call schedule_meeting(email="[the email you collected]", dateTime="[the agreed time]").
Example: If email is "john@gmail.com" and time is "Tuesday at 10am" (from combining "mornings", "10am", "Tuesday"), call schedule_meeting(email="john@gmail.com", dateTime="Tuesday at 10am") RIGHT NOW.

Do not say "let me schedule that" or "I'll create the event" - just call the tool immediately.

Step I: POST-BOOKING FLOW (After schedule_meeting completes successfully)

The Confirmation:
After the schedule_meeting tool completes, say: "Okay, perfect... I just sent that invite over. Let me know when you see it pop up?"

(Pause and wait for their response)

If they say yes / got it / I see it:
Say: "Perfect."

The Google Glitch:
Say: "Okay, cool. Could you do me one quick favor and add it to your calendar right now?"
Say: "Google's been a little weird lately... and sometimes the meeting doesn't sync unless you hit accept."

(Pause)

The Commitment Check:
Say: "Alright, so I've got you down for [the time they agreed to, e.g., 'Tuesday at 10am']. Is there any reason at all you wouldn't be able to make that time?"

(Pause — expect 'no' or 'no reason' or similar)

UPDATED EXIT (more conversational, natural):
Say: "Alright, you should be all set then."
Say: "Thanks {customer_name}... I'll talk to you soon."
Say: "Bye! See you then!"

OBJECTION HANDLING

If they say "no" or "not interested":
"Okay, totally fair. Just out of curiosity... what would have to change for this to make sense?"

Wait for their response.

If they give a specific objection (price, timing, etc.):
Address it directly and naturally, then ask: "Would you be open to a quick 15 or 20 minute chat to see if it makes sense?"

If they still say no:
"Alright, no worries. Thanks for your time. Have a good one."

Then call end_call().

SPECIAL HANDLING

Voicemail Detection:
If you detect a voicemail greeting, IMMEDIATELY call the end_call() tool. Do NOT leave a voicemail message.

"Is this AI?"
"I'm a digital assistant for the team here in San Jose, helping them get in touch with local businesses."
"But I can get a human on the line if you prefer?"

Hostile/Angry:
"Sorry about that, I can take you off the list. Have a good one."
Trigger endCall."""
        
        return {
            "prompt": default_prompt,
            "source": "default",
            "is_default": True
        }
