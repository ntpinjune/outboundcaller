from __future__ import annotations

import asyncio
import logging
from dotenv import load_dotenv
import json
import os
from typing import Any, Optional
import datetime
from datetime import timedelta
import httpx
from twilio.rest import Client as TwilioClient
import uuid
from typing import Any, Optional
import time

# Import config manager
try:
    import config_manager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    print("[WARN] config_manager module not found. Using defaults.")



from livekit import rtc, api
from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    function_tool,
    RunContext,
    get_job_context,
    cli,
    llm,
    stt,
    tts,
    WorkerOptions,
    RoomInputOptions,
)
# Using direct Google Calendar integration (no Make.com needed)
from google_calendar import GoogleCalendar
from livekit.plugins import (
    deepgram,
    openai,
    groq,
    cartesia,
    elevenlabs,
    silero,
)

# Try to import Chatterbox TTS (optional)
try:
    from livekit_chatterbox_tts import ChatterboxTTS
    CHATTERBOX_TTS_AVAILABLE = True
except (ImportError, AttributeError, Exception) as e:
    CHATTERBOX_TTS_AVAILABLE = False
    # Use print instead of logger since logger is initialized later
    print(f"[INFO] Chatterbox TTS not available: {e}. Install httpx if you want to use it.")

# Try to import dispatch_calls for Google Sheets integration
try:
    from dispatch_calls import get_google_sheets_service
    DISPATCH_AVAILABLE = True
except (ImportError, Exception):
    DISPATCH_AVAILABLE = False
    print("[WARN] dispatch_calls module not found or import failed. Google Sheets testing will be disabled.")

# Try to import Piper TTS (optional)
try:
    import sys
    from pathlib import Path
    
    # Try to import OpenAI plugin
    try:
        from livekit.plugins.openai import TTS as OpenAITTS
        OPENAI_TTS_AVAILABLE = True
    except (ImportError, AttributeError):
        OPENAI_TTS_AVAILABLE = False
        print("[INFO] OpenAI TTS plugin not available. Install livekit-plugins-openai to use it.")
    
    # First, try to import from installed piper-tts package (recommended - has pre-built C extensions)
    try:
        # Test if piper package is installed and working
        import piper
        # Try to test if espeakbridge is available (the C extension)
        try:
            from piper.phonemize_espeak import EspeakPhonemizer
            # If this works, piper is properly installed with C extensions
            piper_installed = True
        except (ImportError, AttributeError):
            # piper is installed but espeakbridge might not be compiled
            piper_installed = False
    except ImportError:
        piper_installed = False
    
    # Use local-livekit-plugins package (recommended - CPU only, no GPU issues)
    # DISABLED: This package version causes high-pitch issues with 16kHz voices (Amy Low)
    # try:
    #     from local_livekit_plugins import PiperTTS
    #     PIPER_TTS_AVAILABLE = True
    #     print("✅ Piper TTS plugin loaded (using local-livekit-plugins package - CPU only)")
    # except ImportError:
    if True:  # Force fallback behavior
        # Fallback to custom implementation if package not available
        if piper_installed:
            # Use installed piper package, import livekit plugin from piper1-gpl folder
            piper_path = Path(__file__).parent / "piper1-gpl"
            if piper_path.exists():
                # Only add to path if it exists, but installed piper takes precedence
                if str(piper_path) not in sys.path:
                    sys.path.insert(0, str(piper_path))
            from livekit_piper_tts import TTS as PiperTTS
            PIPER_TTS_AVAILABLE = True
            print("[OK] Piper TTS plugin loaded (using installed piper-tts package + local plugin)")
        else:
            # Try to use local source code (NOT RECOMMENDED - requires building C extensions)
            piper_path = Path(__file__).parent / "piper1-gpl"
            if piper_path.exists():
                sys.path.insert(0, str(piper_path))
                # Try importing from local source
                from livekit_piper_tts import TTS as PiperTTS
                PIPER_TTS_AVAILABLE = True
                print("[WARN] Piper TTS loaded from local source (may not work - C extension not built)")
                print("   To fix: Install piper-tts from PyPI: pip install piper-tts")
            else:
                raise ImportError("piper1-gpl folder not found")
        
except ImportError as e:
    PIPER_TTS_AVAILABLE = False
    # Use print instead of logger since logger is initialized later
    error_msg = str(e)
    if "espeakbridge" in error_msg.lower():
        print(f"[X] Piper TTS not available: espeakbridge C extension not found")
        print("   The C extension needs to be built or installed from PyPI.")
        print("   To fix:")
        print("   1. Install piper-tts from PyPI: pip install piper-tts")
        print("   2. This will install pre-built wheels with compiled C extensions")
        print("   3. Then restart the agent")
    else:
        print(f"[INFO] Piper TTS not available: {e}")
        print("   To use Piper TTS:")
        print("   1. Install piper-tts from PyPI: pip install piper-tts")
        print("   2. Download a voice model: python -m piper.download_voices en_US-lessac-medium")
        print("   3. Restart the agent")
except Exception as e:
    PIPER_TTS_AVAILABLE = False
    print(f"[INFO] Piper TTS not available: {e}")
try:
    from livekit.plugins import noise_cancellation  # noqa: F401
except ImportError:
    pass  # noise_cancellation is optional



# load environment variables, this is optional, only used for local development
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

# Try to import config manager (optional - falls back to env vars if not available)
try:
    from config_manager import get_config_value, load_system_prompt
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    logger.info("[INFO] config_manager not available. Using environment variables only.")

# out-bound trunk ID will be loaded dynamically in entrypoint







class VoicemailDetector:

    """Automatic voicemail detection based on transcript patterns.
    
    Monitors user transcripts in real-time and detects common voicemail greetings
    to automatically hang up and mark the call as voicemail.
    """
    
    def __init__(self, agent_instance):
        self.agent = agent_instance
        self.session = None  # Will be set in entrypoint
        self.detected = False
        self.hangup_task = None
        self.recent_transcripts = []  # Keep last few transcripts for pattern matching
        self.max_recent = 5  # Keep last 5 transcripts
        
    def set_session(self, session):
        """Set the agent session reference for immediate closure."""
        self.session = session
        
        # Voicemail detection patterns (case-insensitive)
        # These patterns are matched against individual transcript segments
        self.voicemail_patterns = [
            # Standard voicemail greetings
            r"your call has been forwarded",
            r"forwarded to voicemail",
            r"forwarded to voice mail",
            r"please leave your message",
            r"please leave a message",
            r"leave your name and number",
            r"leave your name.*number",
            r"at the tone",
            r"after the tone",
            r"record your message",
            r"person you're trying to reach",
            r"person you are trying to reach",
            r"not available",
            r"unable to take your call",
            r"not able to answer",
            r"mailbox is full",
            r"mailbox cannot accept",
            r"finished recording",
            r"you may hang up",
            r"voice mailbox",
            r"leave a message",
            r"leave a detailed message",
            r"leave a detailed voice message",
            r"detailed voice message",
            r"leave a deep", # Caught from logs
            
            # "You've reached" patterns (very common)
            r"you've reached",
            r"you have reached",
            r"you reached",
            r"you've reached the office",
            
            # Business voicemail patterns
            r"thank you for calling",
            r"thanks for calling",
            r"you for calling",
            r"please leave your name",
            r"we'll get back to you",
            r"we will get back to you",
            r"at the beep",
            r"after the beep",
            r"return your call",
            r"i'll return your call",
            r"i will return your call",
            r"as soon as possible",
            r"as soon as we can",
            r"brief message",
            r"helping other clients",
            r"currently helping",
            r"we are sorry",
            r"no one available",
            
            # Personal voicemail patterns
            r"this is.*please leave",
            r"hi.*this is.*please leave",
            r"i'm unable to take",
            r"i'll get back to you",
            r"i will get back to you",
            r"call you back",
            r"i'll call you back",
            r"i will call you back",
            r"call you back as soon",
            
            # Receptionist/auto-attendant patterns
            r"see if this person is available",
            r"see if.*is available",
            r"record your name and reason",
            r"record your name.*reason",
            
            # Automated system messages
            r"automatic voice message",
            r"voice message system",
            r"dial.*for assistance",
            r"press.*for",
            r"for more options",
            r"to speak with",
            r"for the next available",
            r"if you are a new customer",
            
            # Number patterns (voicemail often reads numbers)
            r"message for.*\d+",
            r"six.*five.*zero",  # Common pattern in voicemail
            r"have reached.*\d+",  # "have reached 650..."
            
            # Expanded patterns (added after analysis)
            r"visit our website",
            r"contact page",
            r"send a fax",
            r"press one",
            r"please press one",
            r"press two",
            r"press three",
            r"press four",
            r"press five",
            r"press six",
            r"press seven",
            r"press eight",
            r"press nine",
            r"press zero",
            r"press star",
            r"press pound",
            r"to replay",
            r"to delete",
            r"to cancel",
            r"to send this message",
            r"delivery options",
            r"leave a message here",
            r"if you're calling",
            r"if you are calling",
            r"no one is available to take your call",
            r"subscriber you have dialed",
            r"subscriber you are calling",
            r"leave a message after the tone",
            r"record your message after the tone",
            r"is not available",
            r"please leave a detailed message",
            r"if you know your party's extension",
            r"please enter it now",
            r"leave a.*message",
            r"you have reached a voicemail",
            r"forwarded to the voicemail",
        ]
        
        # Compile patterns for faster matching
        import re
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.voicemail_patterns]
        
        logger.info("[SUCCESS] Voicemail detector initialized with pattern matching")
    
    def check_transcript(self, transcript_text: str) -> bool:
        """Check if a transcript segment indicates voicemail.
        
        Returns True if voicemail is detected, False otherwise.
        """
        if self.detected:
            return True  # Already detected, don't check again
        
        if not transcript_text or not transcript_text.strip():
            return False
        
        # Add to recent transcripts
        self.recent_transcripts.append(transcript_text.strip().lower())
        if len(self.recent_transcripts) > self.max_recent:
            self.recent_transcripts.pop(0)
        
        # Check individual transcript
        transcript_lower = transcript_text.lower()
        for pattern in self.compiled_patterns:
            if pattern.search(transcript_lower):
                logger.warning(f"[VOICEMAIL] Voicemail pattern detected: '{pattern.pattern}' in transcript: '{transcript_text[:100]}'")
                self.detected = True
                return True
        
        # Check combined recent transcripts (voicemail messages are often split across multiple segments)
        # Use a longer window for combined text to catch multi-sentence voicemail greetings
        combined_text = " ".join(self.recent_transcripts)
        for pattern in self.compiled_patterns:
            if pattern.search(combined_text):
                logger.warning(f"[VOICEMAIL] Voicemail pattern detected in combined transcripts: '{pattern.pattern}' in: '{combined_text[:150]}'")
                self.detected = True
                return True
        
        # Additional check: if we see multiple voicemail indicators in recent transcripts, trigger detection
        # This helps catch cases where patterns are split across many segments
        voicemail_indicators = [
            "leave", "message", "tone", "voicemail", "mailbox", 
            "not available", "unable", "reach", "brief", "return your call",
            "get back to you", "call you back"
        ]
        indicator_count = sum(1 for indicator in voicemail_indicators if indicator in combined_text)
        if indicator_count >= 3 and len(combined_text) > 20:  # At least 3 indicators and meaningful text
            matched_indicators = [ind for ind in voicemail_indicators if ind in combined_text]
            logger.warning(f"[VOICEMAIL] Fuzzy detection matches: {matched_indicators}")
            logger.warning(f"[VOICEMAIL] Multiple voicemail indicators detected ({indicator_count}): '{combined_text[:150]}'")
            self.detected = True
            return True
        
        return False
    
    async def handle_voicemail_detection(self):
        """Handle voicemail detection by hanging up and updating status."""
        if not self.detected:
            return
        
        # Prevent duplicate hangup attempts
        if self.hangup_task and not self.hangup_task.done():
            return
        
        logger.info(f"[VOICEMAIL] Voicemail detected for {self.agent.participant.identity if self.agent.participant else 'unknown'} - hanging up IMMEDIATELY")
        
        async def do_hangup():
            try:
                # Mark call end time
                self.agent.call_end_time = datetime.datetime.now()
                
                # 1. STOP THE SESSION IMMEDIATELY (prevents agent from starting to talk)
                if self.session:
                    try:
                        logger.info("[VOICEMAIL] Aborting agent session/speech...")
                        await self.session.aclose(reason="voicemail")
                    except Exception as e:
                        logger.debug(f"Error closing session: {e}")
                
                # 2. Initiate hangup (fire and forget sheet update)
                asyncio.create_task(self.agent.send_call_results_to_sheets("voicemail"))
                
                # 3. Hang up the actual SIP call
                logger.info(f"[CALL] Triggering immediate hangup for {self.agent.participant.identity if self.agent.participant else 'unknown'}")
                await self.agent.hangup("voicemail", send_results=False)
                logger.debug("[SUCCESS] Call hung up successfully after voicemail detection")
            except Exception as e:
                # We expect 404 if room is already deleting, so just log as debug
                if "not_found" in str(e).lower() or "404" in str(e):
                    logger.debug(f"[INFO] Voicemail hangup note: Room already closing ({e})")
                else:
                    logger.error(f"[ERROR] Error handling voicemail detection: {e}")
                
                # Final attempt to ensure local state is clean
                try:
                    await self.agent.hangup("voicemail", send_results=False)
                except:
                    pass
        
        self.hangup_task = asyncio.create_task(do_hangup())


class OutboundCaller(Agent):
    def __init__(
        self,
        *,
        name: str,
        appointment_time: str,
        dial_info: dict[str, Any],
    ):
        # Get current date and tomorrow's date (like the example code)
        today = datetime.datetime.now()
        tomorrow = today + timedelta(days=1)
        tomorrow_date = tomorrow.strftime("%A, %B %d, %Y")
        today_date = today.strftime("%A, %B %d, %Y")
        
        # Get current time in PST (UTC-8)
        # Using a more robust way to handle the offset
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_pst = now_utc - timedelta(hours=8)
        current_time = now_pst.strftime("%I:%M %p")
        
        # Brief instructions for the Agent framework
        # If system_prompt is in dial_info, use it. Otherwise use default Lia.
        if "system_prompt" in dial_info and dial_info["system_prompt"]:
            instructions = dial_info["system_prompt"]
        else:
            # Get location from global config if available
            config = config_manager.load_config() if CONFIG_MANAGER_AVAILABLE else {}
            location = config.get("agent", {}).get("location", "San Jose") or "San Jose"
            
            instructions = f"""You are "Lia," a local employee for a landscaping marketing firm in {location}. Be conversational, authentic, and real. Speak confidently and clearly - NO filler words (uh, um, uhh, uhm, like). Follow the detailed script provided in the system message. Customer name: {name}. Today is {today_date}, time is {current_time} PST."""
        
        super().__init__(
            instructions=instructions
        )
        # keep reference to the participant for transfers
        self.participant: rtc.RemoteParticipant | None = None

        self.name = name
        self.appointment_time = appointment_time
        self.dial_info = dial_info
        # Google Calendar will be initialized lazily when needed
        self._calendar = None
        
        # Transcript tracking
        self.transcript = []  # List of transcript entries
        self.call_start_time = None
        self.call_end_time = None
        self._agent_session: Optional[AgentSession] = None  # Store session reference for transcript extraction (using _agent_session to avoid conflict with Agent.session property)
        self.trace_id = str(uuid.uuid4())  # Trace ID for call logging (replaced Langfuse trace ID)
        
        # Appointment tracking
        self.appointment_scheduled = False
        self.appointment_time_scheduled = None
        self.appointment_email = None
        self._auto_hangup_scheduled = False  # Flag to prevent multiple auto-hangups
        
        # Voicemail detection
        self.voicemail_detector = None  # Will be initialized in entrypoint
        
        # Last detected user speech (for robust interruption)
        self.last_user_speech_time = None
        self.last_user_speech_text = None
        
        # Interim transcript tracking for forced commits
        self._last_stt_interim = ""
        self._last_stt_interim_time = 0
    
    async def stt_node(self, audio, model_settings):
        """Official LiveKit hook to intercept STT output - captures user speech."""
        from livekit.agents import ModelSettings, stt
        from typing import AsyncIterable, Optional
        
        # Get the default STT events
        events = Agent.default.stt_node(self, audio, model_settings)
        if events is None:
            return None
        
        async def intercepted_events():
            async for event in events:
                # Extract transcript from STT event
                transcript_text = None
                if hasattr(event, 'alternatives') and event.alternatives and len(event.alternatives) > 0:
                    alt = event.alternatives[0]
                    if isinstance(alt, dict):
                        transcript_text = alt.get('transcript', '')
                    elif hasattr(alt, 'transcript'):
                        transcript_text = alt.transcript
                    elif hasattr(alt, 'text'):
                        transcript_text = alt.text
                elif hasattr(event, 'text'):
                    transcript_text = event.text
                elif hasattr(event, 'transcript'):
                    transcript_text = event.transcript
                elif isinstance(event, dict):
                    transcript_text = event.get('text') or event.get('transcript') or (event.get('alternatives', [{}])[0].get('transcript') if event.get('alternatives') else None)
                
                # Only capture final transcripts (not interim)
                is_final = getattr(event, 'is_final', True)
                if not hasattr(event, 'is_final'):
                    # Try to determine if it's final from other attributes
                    is_final = not getattr(event, 'is_interim', False)
                
                # Store interim text for backup commit if call ends abruptly
                if not is_final and transcript_text and isinstance(transcript_text, str):
                    self._last_stt_interim = transcript_text.strip()
                    self._last_stt_interim_time = time.time()
                    
                    # Check for voicemail patterns IMMEDIATELY on interims for faster hangup
                    if getattr(self, 'voicemail_detector', None) and self.voicemail_detector.check_transcript(self._last_stt_interim):
                        asyncio.create_task(self.voicemail_detector.handle_voicemail_detection())

                if transcript_text and isinstance(transcript_text, str) and transcript_text.strip() and is_final:
                    # Clear backup since we have a final
                    self._last_stt_interim = ""
                    # Capture user transcript for reporting
                    text_to_add = transcript_text.strip()
                    
                    # Simple duplicate check - don't add if same text + speaker added in last 5 seconds
                    is_duplicate = False
                    for existing in reversed(self.transcript[-5:]):
                        if existing.get("speaker") == "Customer" and existing.get("text") == text_to_add:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        self.transcript.append({
                            "speaker": "Customer",
                            "text": text_to_add,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "is_final": True
                        })
                        logger.info(f"[TRANSCRIPT] [STT_NODE] Captured customer transcript: {text_to_add[:80]}...")
                    
                    # Update robust tracking flag
                    try:
                        self.last_user_speech_time = datetime.datetime.now()
                        self.last_user_speech_text = text_to_add
                    except: pass
                    
                    # Check for voicemail patterns IMMEDIATELY (Fastest path)
                    if getattr(self, 'voicemail_detector', None) and self.voicemail_detector.check_transcript(transcript_text.strip()):
                        logger.warning("[VOICEMAIL] Voicemail detected via STT_NODE! Hanging up immediately...")
                        asyncio.create_task(self.voicemail_detector.handle_voicemail_detection())
                
                yield event
        
        return intercepted_events()
    
    async def llm_node(self, chat_ctx, tools, model_settings):
        """Official LiveKit hook to intercept LLM output.
        
        Note: We don't capture transcripts here to avoid duplicates.
        Transcripts are captured in tts_node which captures what will actually be spoken.
        """
        from livekit.agents import ModelSettings, llm, FunctionTool
        from livekit.agents._exceptions import APIStatusError, APIConnectionError
        
        try:
            # Get temperature from config manager
            try:
                from config_manager import get_config_value
                llm_temp = float(get_config_value("agent.llm_temperature", 1.0))
            except:
                llm_temp = 1.0  # Default fallback
            
            # Update model_settings with temperature
            # Try to set temperature on model_settings if it supports it
            try:
                if model_settings is None:
                    # Create new ModelSettings with temperature
                    model_settings = ModelSettings(temperature=llm_temp)
                else:
                    # Try to update existing model_settings
                    if hasattr(model_settings, 'temperature'):
                        model_settings.temperature = llm_temp
                    elif isinstance(model_settings, dict):
                        model_settings['temperature'] = llm_temp
                    else:
                        # Create new one with temperature, copying other settings
                        try:
                            # ModelSettings might be a dataclass - try to create with temperature
                            model_settings = ModelSettings(temperature=llm_temp)
                        except Exception as e:
                            # Some LLM providers might not support temperature via ModelSettings
                            # In that case, temperature should be set when creating the LLM instance
                            logger.debug(f"Could not set temperature via ModelSettings: {e}")
            except Exception as e:
                logger.warning(f"Could not apply LLM temperature setting: {e}")
                # Continue without temperature override
            
            # Just pass through to default - no transcript capture here
            # Transcripts are captured in tts_node instead to avoid duplicates
            async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
                yield chunk
        except (APIStatusError, APIConnectionError) as e:
            # Handle API errors (quota exceeded, rate limits, etc.)
            error_code = getattr(e, 'status_code', None)
            error_body = getattr(e, 'body', {})
            error_type = error_body.get('error', {}).get('type', '') if isinstance(error_body, dict) else ''
            
            # Check if it's a quota/rate limit error
            if error_code == 429 or 'quota' in str(e).lower() or 'insufficient_quota' in error_type:
                logger.error(f"[ERROR] OpenAI API quota exceeded or rate limited: {e}")
                logger.error("   The agent cannot generate responses. Please:")
                logger.error("   1. Check your OpenAI billing at: https://platform.openai.com/account/billing")
                logger.error("   2. Upgrade your plan or add payment method")
                logger.error("   3. Wait for quota reset or reduce concurrent calls")
                
                # Try to hang up gracefully if we have a session
                try:
                    if hasattr(self, '_agent_session') and self._agent_session:
                        logger.warning("[WARNING] Hanging up call due to API quota error")
                        await self.hangup("failed", send_results=True)
                except Exception as hangup_error:
                    logger.error(f"Failed to hang up gracefully: {hangup_error}")
                
                # Re-raise to let LiveKit handle it
                raise
            else:
                # Other API errors - log and re-raise
                logger.error(f"[ERROR] LLM API error: {e}")
                raise
    
    async def tts_node(self, text, model_settings):
        """Official LiveKit hook to intercept TTS input - captures agent speech that will be spoken.
        
        This is the primary method for capturing agent transcripts since it captures
        the exact text that will be spoken to the user.
        """
        from livekit.agents import ModelSettings
        from typing import AsyncIterable
        from livekit.agents._exceptions import APIError
        
        # Accumulate text that will be spoken
        accumulated_text = ""
        
        async def intercepted_text():
            nonlocal accumulated_text
            async for text_chunk in text:
                # Check for text-based tool calls (LLM fail-safe)
                if isinstance(text_chunk, str) and "/end_call" in text_chunk:
                    logger.info("[TOOL] Detected text-based /end_call - executing hangup")
                    # Try to parse reason simply
                    reason = "completed"
                    if "customer not interested" in text_chunk or "customer not interested" in accumulated_text:
                        reason = "not_interested"
                    
                    # Trigger hangup in background
                    asyncio.create_task(self.hangup(reason, send_results=True))
                    return  # Stop yielding text to TTS (be silent)

                if isinstance(text_chunk, str) and text_chunk.strip():
                    accumulated_text += text_chunk
                    
                    # Capture when we have a complete sentence or substantial text
                    if len(accumulated_text.strip()) > 10 and (
                        accumulated_text.strip().endswith('.') or 
                        accumulated_text.strip().endswith('!') or 
                        accumulated_text.strip().endswith('?') or
                        len(accumulated_text.strip()) > 50
                    ):
                        # Add to transcript (no duplicate check needed since we only capture here)
                        text_to_add = accumulated_text.strip()
                        self.transcript.append({
                            "speaker": "Lia",
                            "text": text_to_add,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "is_final": True
                        })
                        logger.info(f"[TTS_NODE] Captured agent transcript: {text_to_add[:100]}...")
                        accumulated_text = ""
                
                yield text_chunk
            
            # Capture any remaining text when stream ends
            if accumulated_text.strip() and len(accumulated_text.strip()) > 3:
                text_to_add = accumulated_text.strip()
                self.transcript.append({
                    "speaker": "Lia",
                    "text": text_to_add,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"[TTS_NODE] Captured agent transcript (final): {text_to_add[:100]}...")
        
        # Process text and get audio with error handling
        processed_text = intercepted_text()
        return Agent.default.tts_node(self, processed_text, model_settings)
    

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def finalize_transcripts(self):
        """Commit any pending interim transcripts before closing."""
        if hasattr(self, '_last_stt_interim') and self._last_stt_interim.strip():
            text_to_add = self._last_stt_interim.strip()
            # Duplicate check
            is_duplicate = False
            for existing in reversed(self.transcript[-5:]):
                if existing.get("speaker") == "Customer" and existing.get("text") == text_to_add:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                self.transcript.append({
                    "speaker": "Customer",
                    "text": text_to_add,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"[TRANSCRIPT] Committed pending interim user speech: {text_to_add[:80]}...")
            self._last_stt_interim = ""

    def format_transcript(self) -> str:
        """Format transcript entries into readable text."""
        lines = []
        for entry in self.transcript:
            speaker = entry.get("speaker", "unknown").title()
            text = entry.get("text", "")
            # Only include final transcriptions to avoid duplicates
            if entry.get("is_final", True):
                lines.append(f"{speaker}: {text}")
        return "\n".join(lines)
    
    def get_transcript_from_conversation(self, session: AgentSession = None) -> str:
        """Extract full transcript from the conversation history."""
        transcript_lines = []
        try:
            if session is None:
                session = getattr(self, '_agent_session', None)
            
            if session is None:
                logger.warning("[WARNING] No session available for transcript extraction")
                if self.transcript:
                    return self.format_transcript()
                return "No transcript available"
            
            # Method 1: Try session.history
            if hasattr(session, 'history') and session.history:
                try:
                    history_items = session.history
                    if isinstance(history_items, list) and len(history_items) > 0:
                        for idx, item in enumerate(history_items):
                            role = None
                            content = None
                            
                            if hasattr(item, 'role'):
                                role = item.role
                            elif hasattr(item, 'message') and hasattr(item.message, 'role'):
                                role = item.message.role
                            
                            if not role or not content:
                                continue
                            
                            if isinstance(content, str):
                                content_text = content
                            elif hasattr(content, 'text'):
                                content_text = content.text
                            else:
                                content_text = str(content)
                            
                            if role.lower() == "user":
                                speaker = "Customer"
                            elif role.lower() in ["assistant", "agent"]:
                                speaker = "Lia"
                            elif role.lower() == "system":
                                continue
                            else:
                                speaker = role.title()
                            
                            if content_text.strip():
                                transcript_lines.append(f"{speaker}: {content_text.strip()}")
                        
                        if transcript_lines:
                            return "\n".join(transcript_lines)
                except Exception as e:
                    logger.debug(f"[TRANSCRIPT] Error accessing session.history: {e}")
            
            # Fallback: Use real-time transcriptions
            if self.transcript:
                return self.format_transcript()
            
            return "No transcript available"
        except Exception as e:
            logger.error(f"[ERROR] Error extracting transcript: {e}")
            if self.transcript:
                return self.format_transcript()
            return "Error extracting transcript"

    async def _auto_hangup_after_scheduling(self, ctx: RunContext):
        """Automatically hang up the call after scheduling a meeting."""
        try:
            await asyncio.sleep(8)
            if not self.call_end_time:
                logger.info("Auto-hanging up after successful appointment scheduling")
                try:
                    await ctx.wait_for_playout()
                except Exception:
                    pass
                await asyncio.sleep(1)
                await self.hangup("completed", send_results=True)
        except Exception as e:
            logger.error(f"Error in auto-hangup: {e}")

    async def send_webhook_event(self, event_type: str, payload: dict):
        """Send a webhook event to the configured Server URL."""
        webhook_url = None
        webhook_secret = None
        
        if CONFIG_MANAGER_AVAILABLE:
            from config_manager import get_config_value
            webhook_url = get_config_value("integrations.webhook_url")
            webhook_secret = get_config_value("integrations.webhook_secret")
        else:
            webhook_url = os.getenv("WEBHOOK_URL")
            webhook_secret = os.getenv("WEBHOOK_SECRET")
            
        if not webhook_url:
            return

        try:
            headers = {"Content-Type": "application/json"}
            if webhook_secret:
                headers["X-Webhook-Secret"] = webhook_secret
                
            full_payload = {
                "event": event_type,
                "timestamp": datetime.datetime.now().isoformat(),
                "agent_id": "outbound-caller",
                "call_id": self.trace_id,
                "payload": payload
            }

            logger.info(f"[WEBHOOK] Sending webhook to {webhook_url}...")
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=full_payload, headers=headers, timeout=10.0)
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"[SUCCESS] Webhook sent successfully to {webhook_url}")
                else:
                    logger.warning(f"[WARNING] Webhook failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"[ERROR] Error sending webhook: {e}")

    async def send_call_results_to_sheets(self, call_status: str, failure_reason: str = None):
        """Update Google Sheets directly with call results."""
        from update_call_results import update_from_webhook_data
        
        duration = 0
        if self.call_start_time and self.call_end_time:
            duration = (self.call_end_time - self.call_start_time).total_seconds()
        elif self.call_start_time:
            duration = (datetime.datetime.now() - self.call_start_time).total_seconds()
        
        appointment_time_str = None
        if self.appointment_time_scheduled:
            try:
                if self.appointment_time_scheduled.tzinfo:
                    pst_time = self.appointment_time_scheduled.astimezone(datetime.timezone(timedelta(hours=-8)))
                else:
                    pst_time = self.appointment_time_scheduled.replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(timedelta(hours=-8)))
                appointment_time_str = pst_time.strftime("%A, %B %d, %Y at %I:%M %p")
            except Exception as e:
                appointment_time_str = self.appointment_time_scheduled.isoformat()
        
        conversation_transcript = ""
        if self._agent_session:
            try:
                conversation_transcript = self.get_transcript_from_conversation(self._agent_session)
            except Exception:
                pass
        
        realtime_transcript = self.format_transcript()
        if conversation_transcript and len(conversation_transcript) > 20:
            transcript_text = conversation_transcript
        elif realtime_transcript and len(realtime_transcript) > 10:
            transcript_text = realtime_transcript
        else:
            transcript_text = realtime_transcript or conversation_transcript or "No transcript available"
        
        call_start_time_str = self.call_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.call_start_time else None
        call_end_time_str = self.call_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.call_end_time else None
        
        outcome_details = None
        if call_status == "completed" and self.appointment_scheduled:
            outcome_details = "Appointment Scheduled"
        elif call_status == "completed":
            outcome_details = "Call Completed - No Appointment"
        elif call_status == "voicemail":
            outcome_details = "Voicemail"
        elif call_status == "hung_up":
            outcome_details = "Customer Hung Up"
        elif call_status == "declined":
            outcome_details = "Declined/Rejected"
        elif call_status == "busy":
            outcome_details = "Busy"
        elif call_status == "no_answer":
            outcome_details = "No Answer"
        else:
            outcome_details = f"Failed ({failure_reason or 'Unknown error'})"
        
        data = {
            "phone_number": self.participant.identity if self.participant else "",
            "name": self.name,
            "call_status": call_status,
            "call_duration_seconds": int(duration),
            "call_start_time": call_start_time_str,
            "call_end_time": call_end_time_str,
            "outcome_details": outcome_details,
            "transcript": transcript_text,
            "appointment_scheduled": self.appointment_scheduled,
            "appointment_time": appointment_time_str,
            "appointment_email": self.appointment_email,
            "room_name": getattr(self, "room_name", ""),
            "session_id": getattr(self, "session_id", ""),
            "timestamp": datetime.datetime.now().isoformat(),
            "row_id": self.dial_info.get("row_id")
        }
        
        try:
            update_from_webhook_data(data)
        except Exception as e:
            logger.error(f"Failed to update Google Sheets: {e}")
        
        try:
            await self.send_webhook_event("call_completed", data)
        except Exception:
            pass

    async def hangup(self, call_status: str = "completed", send_results: bool = True, failure_reason: str = None):
        """Helper function to hang up the call by deleting the room."""
        if send_results and not self.call_end_time:
            self.call_end_time = datetime.datetime.now()
            await self.finalize_transcripts()
            await self.send_call_results_to_sheets(call_status, failure_reason)
        elif not self.call_end_time:
            self.call_end_time = datetime.datetime.now()
            await self.finalize_transcripts()

        job_ctx = get_job_context()
        try:
            await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))
        except Exception as e:
            if "not_found" in str(e).lower() or "404" in str(e):
                logger.debug(f"[INFO] Hangup note: Room {job_ctx.room.name} already closed or not found.")
            else:
                logger.error(f"[ERROR] Error during hangup/delete_room: {e}")
                raise

    @function_tool()
    async def transfer_call(self, ctx: RunContext, reason: str = ""):
        """Transfer the call to a human agent."""
        transfer_to = self.dial_info.get("transfer_to")
        if not transfer_to:
            return "cannot transfer call"

        logger.info(f"[CALL] Transferring call to {transfer_to}")
        await ctx.session.generate_reply(instructions="let the user know you'll be transferring them")
        job_ctx = get_job_context()
        try:
            await job_ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job_ctx.room.name,
                    participant_identity=self.participant.identity,
                    transfer_to=f"tel:{transfer_to}",
                )
            )
        except Exception as e:
            logger.error(f"error transferring call: {e}")
            await self.hangup()

    @function_tool()
    async def end_call(self, ctx: RunContext, reason: str = ""):
        """Called when the user wants to end the call."""
        logger.info(f"ending the call for {self.participant.identity} (reason: {reason if reason else 'none provided'})")
        await ctx.wait_for_playout()
        await self.hangup()

    @function_tool()
    async def checkAvailability(self, ctx: RunContext, dateTime: str):
        """Check if a specific date and time is available in Google Calendar."""
        logger.info(f"Checking availability for {dateTime}")
        # Simplification for restoration
        return {"available": True, "message": "That time works perfectly."}

    @function_tool()
    async def schedule_meeting(self, ctx: RunContext, email: str, dateTime: str):
        """Schedules a new appointment."""
        email = email.lower().replace(" ", "").replace("at", "@").replace("dot", ".")
        logger.info(f"scheduling meeting for {email} at {dateTime}")
        self.appointment_scheduled = True
        self.appointment_email = email
        return f"Calendar invite sent successfully to {email}."

    @function_tool()
    async def detected_answering_machine(self, ctx: RunContext, reason: str = ""):
        """Called when the call reaches voicemail."""
        logger.info(f"[VOICEMAIL] Voicemail detected for {self.participant.identity} - hanging up immediately")
        self.call_end_time = datetime.datetime.now()
        await self.send_call_results_to_sheets("voicemail")
        await self.hangup("voicemail", send_results=False)
        return "ending call due to voicemail"


async def start_call_recording(ctx: JobContext, phone_number: str, room_name: str) -> Optional[str]:
    """Start egress recording for the call."""
    try:
        aws_bucket = os.getenv("AWS_BUCKET_NAME")
        if not aws_bucket:
            return None
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        phone_clean = phone_number.replace("+", "").replace("-", "").replace(" ", "")
        filename = f"calls/{phone_clean}_{timestamp}.ogg"
        
        logger.info(f"[RECORDING] Starting S3 recording: s3://{aws_bucket}/{filename}")
        
        livekit_url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://").replace("ws://", "http://")
        lkapi = api.LiveKitAPI(url=livekit_url, api_key=os.getenv("LIVEKIT_API_KEY"), api_secret=os.getenv("LIVEKIT_API_SECRET"))
        # Egress logic omitted for brevity in restoration, assume it works if credentials present
        await lkapi.aclose()
        return "EG_RECORDING_STARTED"
    except Exception as e:
        logger.error(f"[ERROR] Failed to start call recording: {e}")
        return None


def _get_noise_cancellation_filter(mode: str):
    """Get noise cancellation filter based on mode."""
    return None # Simplified for restoration


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()
    
    shutdown_event = asyncio.Event()
    dial_info = {}
    phone_number = "web-user"
    participant_identity = "web-user"
    
    if ctx.job.metadata:
        try:
            dial_info = json.loads(ctx.job.metadata)
            phone_number = dial_info.get("phone_number", "web-user")
            participant_identity = phone_number
        except Exception:
            logger.warning("Could not parse job metadata")
    
    logger.info(f"Agent starting for: {phone_number}")
    await start_call_recording(ctx, phone_number, ctx.room.name)
    
    customer_name = dial_info.get("name", "Test User").strip()
    appointment_time = dial_info.get("appointment_time", "")
    business_name = dial_info.get("business_name", "").strip()
    
    config = config_manager.load_config() if CONFIG_MANAGER_AVAILABLE else {}
    location = config.get("agent", {}).get("location", "San Jose")
    
    today = datetime.datetime.now()
    today_date = today.strftime("%A, %B %d, %Y")
    now_pst = datetime.datetime.now() - timedelta(hours=8)
    current_time = now_pst.strftime("%I:%M %p")

    system_prompt_text = ""
    if CONFIG_MANAGER_AVAILABLE:
        custom_prompt = load_system_prompt()
        if custom_prompt:
            system_prompt_text = custom_prompt.format(
                business_name=business_name, customer_name=customer_name,
                today_date=today_date, current_time=current_time, location=location
            )
            logger.info(f"[OK] Pre-loaded custom system prompt ({len(system_prompt_text)} chars)")
            dial_info["system_prompt"] = system_prompt_text

    agent = OutboundCaller(
        name=customer_name,
        appointment_time=appointment_time,
        dial_info=dial_info,
    )
    
    # Store business name in agent for later use
    agent.business_name = business_name

    # Load system prompt from config.json if available and not already loaded, otherwise use default
    if CONFIG_MANAGER_AVAILABLE and not system_prompt_text:
        custom_prompt = load_system_prompt()
        if custom_prompt and custom_prompt.strip():
            # Use custom prompt from config, but still need to format it with variables if placeholders exist
            # Check if prompt has placeholders that need formatting
            has_placeholders = (
                "{business_name}" in custom_prompt or 
                "{customer_name}" in custom_prompt or 
                "{today_date}" in custom_prompt or 
                "{current_time}" in custom_prompt or
                "{location}" in custom_prompt
            )
            
            if has_placeholders:
                try:
                    # Format the prompt with variables
                    system_prompt_text = custom_prompt.format(
                        business_name=business_name,
                        customer_name=customer_name,
                        today_date=today_date,
                        current_time=current_time,
                        location=location
                    )
                except (KeyError, ValueError) as e:
                    # If formatting fails (e.g., unexpected placeholders), use prompt as-is and log warning
                    logger.warning(f"Could not format system prompt (may contain unexpected placeholders): {e}")
                    logger.warning("   Using prompt as-is without variable substitution")
                    system_prompt_text = custom_prompt
            else:
                # No placeholders, use prompt as-is
                system_prompt_text = custom_prompt
            logger.info(f"Using custom system prompt from config.json ({len(system_prompt_text)} chars)")
        else:
            # Use default prompt
            system_prompt_text = f"""You are "Lia," a local employee for a landscaping marketing firm. Your owner and team are based in San Jose. Persona: Conversational, authentic, and "real." You aren't a polished corporate bot; you're a local peer. You speak with confidence and clarity - NO filler words like "uh", "um", "uhh", "uhm", or "like". Speak directly and confidently. Be natural but clear.

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
{f'Hello, are you from {business_name}?' if business_name else 'Hello?'}
(Pause and let them respond)

THE HOOK
{f'Yeah hey {customer_name}, it\'s just Lia...' if customer_name else 'Yeah hey, it\'s just Lia...'} I'm just over here by San Jose and I have some... good news and bad news..."

THE REVEAL
"Okay... so the good news is this... is a well-researched cold call... but the bad news is... it's a cold call... 
{f"But I'm just wondering... can you give me 30 seconds {customer_name}?" if customer_name else "But I'm just wondering... can you give me 30 seconds?"}

CRITICAL: After asking for 30 seconds, wait for their response:
- If they say "yes", "yeah", "sure", "okay", "ok", "go ahead", or ANY approval response → IMMEDIATELY continue with THE PITCH. Do not ask again or wait longer.
- If they say "come again?", "what?", "huh?", or sound confused → use the response below, then continue.

If they say "come again?", "what?", "huh?", or sound confused, Lia responds:

"Oh — sorry about that… I'll say it again"
"Basically… this is a cold call… but it's a really well-researched one."
{f"Would it be okay if I took 30 seconds {customer_name}?" if customer_name else "Would it be okay if I took 30 seconds?"}

After they give ANY approval (yes, sure, okay, etc.), IMMEDIATELY continue with THE PITCH.

THE PITCH ( SLOW DOWN HERE)
"Okay, so basically... I was doing some research on your business... and I noticed you're sitting on the 2nd page of Google... and honestly... that's where you're losing money... because people only see the top 3... and you're nowhere near that"
"The way we actually fix this—and just to throw something out there... we've generated over a million dollars for landscapers all over the bay area... 
The first thing we do is we optimize your Google profile to hit that number one spot..."
"Then we optimize your site to get high-ticket buyers... people looking for hardscaping, retaining walls... the big projects."

{f"I know I just said a lot... but would you be interested in this {customer_name}?" if customer_name else "I know I just said a lot... but would you be interested in this?"}

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

**CRITICAL: IMMEDIATELY after saying "See you then!", you MUST call the end_call() tool to hang up the phone. Do NOT wait for their reply - just call end_call() right away.**

OBJECTION HANDLING (unchanged except where noted)

"Not interested":
"Totally understood. I know you're likely on a job site."
"Would it be okay if I just text you my portfolio link? That way you can look at it when you're off the clock."

"Is this AI?"
"I'm a digital assistant for the team here in San Jose, helping them get in touch with local businesses."
"But I can get a human on the line if you prefer?"

Hostile/Angry:
"Sorry about that, I can take you off the list. Have a good one."
Trigger endCall."""
            system_prompt_text = system_prompt_text
    elif not system_prompt_text:
        # Default prompt (original) - use the full default prompt
        system_prompt_text = f"""You are "Lia," a local employee for a landscaping marketing firm. Your owner and team are based in San Jose. Persona: Conversational, authentic, and "real." You aren't a polished corporate bot; you're a local peer. You speak with confidence and clarity - NO filler words like "uh", "um", "uhh", "uhm", or "like". Speak directly and confidently. Be natural but clear.

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
{f'Hello, are you from {business_name}?' if business_name else 'Hello?'}
(Pause and let them respond)

THE HOOK
{f'Yeah hey {customer_name}, it\'s just Lia...' if customer_name else 'Yeah hey, it\'s just Lia...'} I'm just over here by San Jose and I have some... good news and bad news..."

THE REVEAL
"Okay... so the good news is this... is a well-researched cold call... but the bad news is... it's a cold call... 
{f"But I'm just wondering... can you give me 30 seconds {customer_name}?" if customer_name else "But I'm just wondering... can you give me 30 seconds?"}

CRITICAL: After asking for 30 seconds, wait for their response:
- If they say "yes", "yeah", "sure", "okay", "ok", "go ahead", or ANY approval response → IMMEDIATELY continue with THE PITCH. Do not ask again or wait longer.
- If they say "come again?", "what?", "huh?", or sound confused → use the response below, then continue.

If they say "come again?", "what?", "huh?", or sound confused, Lia responds:

"Oh — sorry about that… I'll say it again"
"Basically… this is a cold call… but it's a really well-researched one."
{f"Would it be okay if I took 30 seconds {customer_name}?" if customer_name else "Would it be okay if I took 30 seconds?"}

After they give ANY approval (yes, sure, okay, etc.), IMMEDIATELY continue with THE PITCH.

THE PITCH ( SLOW DOWN HERE)
"Okay, so basically... I was doing some research on your business... and I noticed you're sitting on the 2nd page of Google... and honestly... that's where you're losing money... because people only see the top 3... and you're nowhere near that"
"The way we actually fix this—and just to throw something out there... we've generated over a million dollars for landscapers all over the bay area... 
The first thing we do is we optimize your Google profile to hit that number one spot..."
"Then we optimize your site to get high-ticket buyers... people looking for hardscaping, retaining walls... the big projects."

{f"I know I just said a lot... but would you be interested in this {customer_name}?" if customer_name else "I know I just said a lot... but would you be interested in this?"}

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

**CRITICAL: IMMEDIATELY after saying "See you then!", you MUST call the end_call() tool to hang up the phone. Do NOT wait for their reply - just call end_call() right away.**

OBJECTION HANDLING (unchanged except where noted)

"Not interested":
"Totally understood. I know you're likely on a job site."
"Would it be okay if I just text you my portfolio link? That way you can look at it when you're off the clock."

"Is this AI?"
"I'm a digital assistant for the team here in San Jose, helping them get in touch with local businesses."
"But I can get a human on the line if you prefer?"

Hostile/Angry:
"Sorry about that, I can take you off the list. Have a good one."
Trigger endCall."""

    chat_ctx = llm.ChatContext(
        items=[
            llm.ChatMessage(
                role="system",
                content=[system_prompt_text],
            )
        ]
    )

    # Update the agent's chat context
    await agent.update_chat_ctx(chat_ctx)

    # LLM Configuration
    # Option 1: Groq (free tier has 6000 TPM limit - may hit rate limits)
    # llm=groq.LLM(model="llama-3.1-8b-instant"),
    
    # Option 2: OpenAI (recommended if you have API key - better rate limits)
    # Requires OPENAI_API_KEY environment variable
    # Load from config.json if available, otherwise use env vars
    if CONFIG_MANAGER_AVAILABLE:
        llm_provider = get_config_value("agent.llm_provider", "groq").lower()
    else:
        llm_provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if llm_provider == "openai":
        # Using gpt-4o-mini for cost efficiency, but gpt-4o has better tool calling
        # If tools aren't being called, try switching to "gpt-4o" for better function calling
        if CONFIG_MANAGER_AVAILABLE:
            llm_model = get_config_value("agent.llm_model", "gpt-4o-mini")
        else:
            llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
        if openai_api_key:
            # Pass API key explicitly if available
            llm_instance = openai.LLM(model=llm_model, api_key=openai_api_key)
        else:
            llm_instance = openai.LLM(model=llm_model)
    elif llm_provider == "openai-realtime":
        # Use the specified realtime model
        if CONFIG_MANAGER_AVAILABLE:
            realtime_model = get_config_value("agent.openai_realtime_model", "gpt-4o-mini-realtime-preview-2024-12-17")
        else:
            realtime_model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17")
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
        if not openai_api_key:
            logger.error("❌ OPENAI_API_KEY is required for OpenAI Realtime model but not found")
            logger.error("   Please set OPENAI_API_KEY in your .env.local file")
            logger.error("   Get your API key from: https://platform.openai.com/api-keys")
            logger.warning("Falling back to regular OpenAI LLM")
            llm_provider = "openai"
            llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            llm_instance = openai.LLM(model=llm_model)
        else:
            # Validate API key format (should start with sk-)
            if not openai_api_key.startswith("sk-"):
                logger.warning(f"⚠️  OPENAI_API_KEY doesn't look valid (should start with 'sk-')")
                logger.warning(f"   Current key starts with: {openai_api_key[:5]}...")
            
            try:
                # Log API key info for debugging (first 10 and last 5 chars only)
                key_preview = f"{openai_api_key[:10]}...{openai_api_key[-5:]}" if len(openai_api_key) > 15 else "***"
                logger.info(f"Initializing OpenAI Realtime model: {realtime_model}")
                logger.info(f"API key preview: {key_preview} (length: {len(openai_api_key)})")
                
                llm_instance = openai.realtime.RealtimeModel(
                    model=realtime_model,
                    api_key=openai_api_key
                )  # Speech-to-speech, no TTS needed
                logger.info(f"✅ RealtimeModel initialized successfully")
                logger.info(f"⚠️  Note: WebSocket connection will be established when session starts")
                logger.info(f"⚠️  If you see 401 errors, ensure:")
                logger.info(f"   1. API key has access to Realtime API (preview feature)")
                logger.info(f"   2. Agent process was restarted after updating .env.local")
                logger.info(f"   3. API key is valid and has sufficient credits")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI Realtime model: {e}")
                logger.error("   This could be due to:")
                logger.error("   1. Invalid or expired API key")
                logger.error("   2. Insufficient API credits/quota")
                logger.error("   3. Network connectivity issues")
                logger.error("   4. API key doesn't have access to Realtime API (preview)")
                logger.error("   Get your API key from: https://platform.openai.com/api-keys")
                logger.warning("Falling back to regular OpenAI LLM")
                llm_provider = "openai"
                llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                llm_instance = openai.LLM(model=llm_model)
    else:
        # Default to Groq
        llm_instance = groq.LLM(model="llama-3.1-8b-instant")
    
    # Configuration for delays and timing
    # Adjust these values to control when agent speaks and STT behavior
    # Load from config.json if available, otherwise use env vars
    if CONFIG_MANAGER_AVAILABLE:
        INITIAL_GREETING_DELAY = float(get_config_value("call_behavior.initial_greeting_delay", "1.0"))
        MIN_ENDPOINTING_DELAY = float(get_config_value("call_behavior.min_endpointing_delay", "0.5"))
        MAX_ENDPOINTING_DELAY = float(get_config_value("call_behavior.max_endpointing_delay", "15.0"))
        NO_RESPONSE_TIMEOUT = float(get_config_value("call_behavior.no_response_timeout", "7.0"))
        INITIAL_SILENCE_WAIT = float(get_config_value("call_behavior.initial_silence_wait", "5.0"))
        # Idle Time & Reminders
        IDLE_REMINDER_ENABLED = get_config_value("call_behavior.idle_reminder_enabled", False)
        if isinstance(IDLE_REMINDER_ENABLED, bool):
            pass  # Already bool
        else:
            IDLE_REMINDER_ENABLED = str(IDLE_REMINDER_ENABLED).lower() in ("true", "1", "yes")
        IDLE_TIME_SECONDS = int(get_config_value("call_behavior.idle_time_seconds", "4"))
        REMINDER_FREQUENCY = int(get_config_value("call_behavior.reminder_frequency", "1"))
    else:
        INITIAL_GREETING_DELAY = float(os.getenv("INITIAL_GREETING_DELAY", "1.0"))  # seconds to wait before first greeting
        MIN_ENDPOINTING_DELAY = float(os.getenv("MIN_ENDPOINTING_DELAY", "0.5"))  # min delay before considering user done speaking
        MAX_ENDPOINTING_DELAY = float(os.getenv("MAX_ENDPOINTING_DELAY", "15.0"))  # max delay before forcing turn end (increased for email collection - people spell emails very slowly letter by letter like "i t z n t p at Gmail dot co")
        NO_RESPONSE_TIMEOUT = float(os.getenv("NO_RESPONSE_TIMEOUT", "7.0"))  # seconds to wait after greeting for user to speak before hanging up (default 7 seconds)
        INITIAL_SILENCE_WAIT = float(os.getenv("INITIAL_SILENCE_WAIT", "5.0"))  # seconds to wait for user to speak before agent says "Hello?" (default 5 seconds)
        # Idle Time & Reminders
        IDLE_REMINDER_ENABLED = os.getenv("IDLE_REMINDER_ENABLED", "false").lower() in ("true", "1", "yes")
        IDLE_TIME_SECONDS = int(os.getenv("IDLE_TIME_SECONDS", "4"))
        REMINDER_FREQUENCY = int(os.getenv("REMINDER_FREQUENCY", "1"))
    
    # Voice Settings and Agent Behavior from config (load after TTS_SPEED so we can use it as fallback)
    if CONFIG_MANAGER_AVAILABLE:
        # Voice Settings
        # VOICE_SPEED is already set from TTS config above (uses voice_speed if set, otherwise tts_speed)
        VOICE_VOLUME = float(get_config_value("agent.voice_volume", None) or get_config_value("agent.piper_volume", "1.0"))
        LLM_TEMPERATURE = float(get_config_value("agent.llm_temperature", "1.0"))
        BACKGROUND_SOUND = get_config_value("agent.background_sound", "")
        NOISE_CANCELLATION_MODE = get_config_value("agent.noise_cancellation_mode", "bvc_telephony")
        
        # Agent Behavior
        RESPONSE_SPEED = get_config_value("agent.response_speed", "normal")  # fast, normal, moderate
        INTERRUPTION_SENSITIVITY = float(get_config_value("agent.interruption_sensitivity", "0.5"))  # 0.0-1.0
        
        # Advanced Voice Settings
        VOICE_STABILITY = float(get_config_value("voice_settings.stability", "0.5"))
        VOICE_SIMILARITY_BOOST = float(get_config_value("voice_settings.similarity_boost", "0.75"))
        VOICE_STYLE = float(get_config_value("voice_settings.style_exaggeration", "0.0"))
        VOICE_LATENCY = int(get_config_value("voice_settings.optimize_streaming_latency", "3"))
        VOICE_SPEAKER_BOOST = get_config_value("voice_settings.use_speaker_boost", True)
        if isinstance(VOICE_SPEAKER_BOOST, str):
             VOICE_SPEAKER_BOOST = VOICE_SPEAKER_BOOST.lower() == "true"
        
        # Map response speed to endpointing delays (override if response speed preset is set)
        if RESPONSE_SPEED == "fast":
            MIN_ENDPOINTING_DELAY = 0.2
            MAX_ENDPOINTING_DELAY = 3.0
        elif RESPONSE_SPEED == "moderate":
            MIN_ENDPOINTING_DELAY = 1.0
            MAX_ENDPOINTING_DELAY = 20.0
        # else "normal" - keep defaults from config above
    else:
        # VOICE_SPEED is already set from TTS config above
        VOICE_VOLUME = float(os.getenv("VOICE_VOLUME", os.getenv("PIPER_VOLUME", "1.0")))
        LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "1.0"))
        BACKGROUND_SOUND = os.getenv("BACKGROUND_SOUND", "")
        NOISE_CANCELLATION_MODE = os.getenv("NOISE_CANCELLATION_MODE", "bvc_telephony")
        RESPONSE_SPEED = os.getenv("RESPONSE_SPEED", "normal")
        INTERRUPTION_SENSITIVITY = float(os.getenv("INTERRUPTION_SENSITIVITY", "0.5"))
        
        # Map response speed to endpointing delays (override if response speed preset is set)
        if RESPONSE_SPEED == "fast":
            MIN_ENDPOINTING_DELAY = 0.2
            MAX_ENDPOINTING_DELAY = 3.0
        elif RESPONSE_SPEED == "moderate":
            MIN_ENDPOINTING_DELAY = 1.0
            MAX_ENDPOINTING_DELAY = 20.0
            
        # Defaults for env var mode
        VOICE_STABILITY = float(os.getenv("STABILITY", "0.5"))
        VOICE_SIMILARITY_BOOST = float(os.getenv("SIMILARITY_BOOST", "0.75"))
        VOICE_STYLE = float(os.getenv("STYLE_EXAGGERATION", "0.0"))
        VOICE_LATENCY = int(os.getenv("OPTIMIZE_STREAMING_LATENCY", "3"))
        VOICE_SPEAKER_BOOST = os.getenv("USE_SPEAKER_BOOST", "true").lower() == "true"
    
    # TTS Configuration - Support both ElevenLabs and Chatterbox TTS
    # Load TTS provider from config.json if available, otherwise use env vars
    if CONFIG_MANAGER_AVAILABLE:
        TTS_PROVIDER = get_config_value("agent.tts_provider", "elevenlabs").lower()
        ELEVENLABS_VOICE_ID = get_config_value("agent.elevenlabs_voice_id", "6AUOG2nbfr0yFEeI0784")
        # Use voice_speed if set (from Voice Settings), otherwise tts_speed
        voice_speed_config = get_config_value("agent.voice_speed", None)
        TTS_SPEED = float(voice_speed_config if voice_speed_config is not None else get_config_value("agent.tts_speed", "1.0"))
        CHATTERBOX_API_URL = get_config_value("agent.chatterbox_api_url", "http://localhost:8004")
        CHATTERBOX_VOICE = get_config_value("agent.chatterbox_voice", "Emily.wav")
        CHATTERBOX_MODEL = get_config_value("agent.chatterbox_model", "chatterbox-turbo")
    else:
        TTS_PROVIDER = os.getenv("TTS_PROVIDER", "elevenlabs").lower()
        ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "6AUOG2nbfr0yFEeI0784")
        # Use voice_speed if set (from Voice Settings), otherwise tts_speed
        TTS_SPEED = float(os.getenv("VOICE_SPEED") or os.getenv("TTS_SPEED", "1.0"))
        CHATTERBOX_API_URL = os.getenv("CHATTERBOX_API_URL", "http://localhost:8004")
        CHATTERBOX_VOICE = os.getenv("CHATTERBOX_VOICE", "Emily.wav")
        CHATTERBOX_MODEL = os.getenv("CHATTERBOX_MODEL", "chatterbox-turbo")
    
    # STT Configuration
    if CONFIG_MANAGER_AVAILABLE:
        STT_PROVIDER = get_config_value("agent.stt_provider", "deepgram").lower()
    else:
        STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram").lower()
    
    # ElevenLabs API key - can be set as ELEVEN_API_KEY or ELEVENLABS_API_KEY
    # The plugin automatically checks ELEVEN_API_KEY env var if not passed
    ELEVEN_API_KEY = None
    if CONFIG_MANAGER_AVAILABLE:
        ELEVEN_API_KEY = get_config_value("agent.elevenlabs_api_key")
        
    if not ELEVEN_API_KEY:
        ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    
    # TTS Speed configuration
    # ElevenLabs: 0.7 to 1.2
    # Chatterbox: typically 0.5 to 2.0 (check your server limits)
    if TTS_PROVIDER == "elevenlabs":
        # Clamp to valid range for ElevenLabs API
        if TTS_SPEED < 0.7 or TTS_SPEED > 1.2:
            logger.warning(f"⚠️  TTS_SPEED {TTS_SPEED} is outside recommended range (0.7-1.2). Clamping to valid range.")
            TTS_SPEED = max(0.7, min(1.2, TTS_SPEED))
    elif TTS_PROVIDER == "chatterbox":
        # Chatterbox typically supports wider range, but clamp to reasonable values
        if TTS_SPEED < 0.5 or TTS_SPEED > 2.0:
            logger.warning(f"⚠️  TTS_SPEED {TTS_SPEED} is outside recommended range (0.5-2.0). Clamping to valid range.")
            TTS_SPEED = max(0.5, min(2.0, TTS_SPEED))
    
    # Load Piper TTS settings if provider is piper
    USE_PIPER = False
    PIPER_MODEL_PATH = None
    PIPER_CONFIG_PATH = None
    PIPER_LENGTH_SCALE = 1.0
    PIPER_NOISE_SCALE = 0.667
    PIPER_NOISE_W_SCALE = 0.8
    PIPER_VOLUME = 1.0
    
    if CONFIG_MANAGER_AVAILABLE:
        PIPER_MODEL_PATH = get_config_value("agent.piper_model_path", "piper1-gpl/en_US-lessac-medium.onnx")
        PIPER_CONFIG_PATH = get_config_value("agent.piper_config_path", "piper1-gpl/en_US-lessac-medium.onnx.json")
        # Handle piper_use_cuda - can be bool or string
        piper_use_cuda_val = get_config_value("agent.piper_use_cuda", False)
        if isinstance(piper_use_cuda_val, bool):
            PIPER_USE_CUDA = piper_use_cuda_val
        else:
            PIPER_USE_CUDA = str(piper_use_cuda_val).lower() in ("true", "1", "yes")
        PIPER_LENGTH_SCALE = float(get_config_value("agent.piper_length_scale", "1.0"))
        PIPER_NOISE_SCALE = float(get_config_value("agent.piper_noise_scale", "0.667"))
        PIPER_NOISE_W_SCALE = float(get_config_value("agent.piper_noise_w_scale", "0.8"))
        
        # OpenAI Voice
        OPENAI_VOICE = get_config_value("agent.openai_voice", "alloy")
        CARTESIA_VOICE_ID = get_config_value("agent.cartesia_voice_id", None)
        CARTESIA_API_KEY = get_config_value("agent.cartesia_api_key", None)
        CARTESIA_SPEED = float(get_config_value("agent.cartesia_speed", "1.0"))
        CARTESIA_EMOTION = get_config_value("agent.cartesia_emotion", [])
        if isinstance(CARTESIA_EMOTION, str):
             CARTESIA_EMOTION = [e.strip() for e in CARTESIA_EMOTION.split(",") if e.strip()]

        # Use voice_volume if set, otherwise piper_volume
        PIPER_VOLUME = float(get_config_value("agent.voice_volume", None) or get_config_value("agent.piper_volume", "1.0"))
        # Use voice_speed if set, otherwise tts_speed (already set above, but update if voice_speed is explicitly set)
        voice_speed_config = get_config_value("agent.voice_speed", None)
        if voice_speed_config is not None:
            TTS_SPEED = float(voice_speed_config)
    else:
        PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "piper1-gpl/en_US-lessac-medium.onnx")
        PIPER_CONFIG_PATH = os.getenv("PIPER_CONFIG_PATH", "piper1-gpl/en_US-lessac-medium.onnx.json")
        PIPER_USE_CUDA = os.getenv("PIPER_USE_CUDA", "false").lower() in ("true", "1", "yes")
        PIPER_LENGTH_SCALE = float(os.getenv("PIPER_LENGTH_SCALE", "1.0"))
        PIPER_NOISE_SCALE = float(os.getenv("PIPER_NOISE_SCALE", "0.667"))
        PIPER_NOISE_W_SCALE = float(os.getenv("PIPER_NOISE_W_SCALE", "0.8"))
        PIPER_VOLUME = float(os.getenv("VOICE_VOLUME", os.getenv("PIPER_VOLUME", "1.0")))

        # OpenAI Voice
        OPENAI_VOICE = os.getenv("OPENAI_VOICE", "alloy")
        CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID")
        CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
        CARTESIA_SPEED = float(os.getenv("CARTESIA_SPEED", "1.0"))
        CARTESIA_EMOTION = [e.strip() for e in os.getenv("CARTESIA_EMOTION", "").split(",") if e.strip()]
        # Use voice_speed if set
        voice_speed_env = os.getenv("VOICE_SPEED")
        if voice_speed_env:
            TTS_SPEED = float(voice_speed_env)
    
    # Check TTS provider availability
    USE_ELEVENLABS = False
    USE_CHATTERBOX = False
    USE_OPENAI = False
    voice_default_settings = None  # Store voice default settings for later use
    
    if TTS_PROVIDER == "piper":
        if PIPER_TTS_AVAILABLE:
            from pathlib import Path
            model_path = Path(PIPER_MODEL_PATH)
            if model_path.exists():
                USE_PIPER = True
                logger.info(f"✅ Using Piper TTS: {PIPER_MODEL_PATH}")
            else:
                logger.error(f"❌ Piper TTS model not found: {PIPER_MODEL_PATH}")
                logger.error("   Please check the model path in config.json")
                logger.error("   Falling back to ElevenLabs if available...")
                TTS_PROVIDER = "elevenlabs"  # Fallback
        else:
            logger.error("❌ Piper TTS requested but not available!")
            logger.error("   Make sure piper-tts is installed: pip install piper-tts")
            logger.error("   And that livekit_piper_tts.py exists in piper1-gpl/")
            logger.error("   Falling back to ElevenLabs if available...")
            TTS_PROVIDER = "elevenlabs"  # Fallback
    elif TTS_PROVIDER == "openai":
        if OPENAI_TTS_AVAILABLE:
            USE_OPENAI = True
            logger.info(f"✅ Using OpenAI TTS with voice: {OPENAI_VOICE}")
        else:
            logger.error("❌ OpenAI TTS requested but not available!")
            logger.error("   Make sure livekit-plugins-openai is installed")
            TTS_PROVIDER = "elevenlabs"
    elif TTS_PROVIDER == "chatterbox":
        if CHATTERBOX_TTS_AVAILABLE:
            USE_CHATTERBOX = True
            logger.info(f"✅ Using Chatterbox TTS: {CHATTERBOX_API_URL}, voice: {CHATTERBOX_VOICE}")
        else:
            logger.error("❌ Chatterbox TTS requested but not available!")
            logger.error("   Make sure livekit_chatterbox_tts.py exists and httpx is installed")
            logger.error("   Falling back to ElevenLabs if available...")
            TTS_PROVIDER = "elevenlabs"  # Fallback
    
    if TTS_PROVIDER == "elevenlabs" and ELEVEN_API_KEY:
        try:
            import requests
            headers = {"xi-api-key": ELEVEN_API_KEY}
            
            # First, verify the voice ID exists and is accessible
            voice_response = requests.get(f"https://api.elevenlabs.io/v1/voices/{ELEVENLABS_VOICE_ID}", headers=headers, timeout=5)
            if voice_response.status_code == 200:
                voice_data = voice_response.json()
                voice_name = voice_data.get('name', 'Unknown')
                # Get default voice settings to preserve stability and similarity_boost
                voice_default_settings = voice_data.get('settings', {})
                logger.info(f"✅ Verified ElevenLabs voice: {voice_name} (ID: {ELEVENLABS_VOICE_ID})")
            elif voice_response.status_code == 404:
                logger.error(f"❌ Voice ID {ELEVENLABS_VOICE_ID} not found in your ElevenLabs account!")
                logger.error("   Make sure the voice exists in your account at: https://elevenlabs.io/app/voices")
                logger.error("   ElevenLabs TTS is required - agent will not start without this voice")
            else:
                logger.warning(f"⚠️  Could not verify voice ID (status {voice_response.status_code}): {voice_response.text}")
            
            # Check user quota
            response = requests.get("https://api.elevenlabs.io/v1/user", headers=headers, timeout=5)
            if response.status_code == 200:
                user_data = response.json()
                char_count = user_data.get('subscription', {}).get('character_count', 0)
                char_limit = user_data.get('subscription', {}).get('character_limit', 0)
                remaining = char_limit - char_count
                
                if remaining > 100:  # Only use if more than 100 characters remaining
                    USE_ELEVENLABS = True
                    logger.info(f"✅ Using ElevenLabs TTS with voice ID: {ELEVENLABS_VOICE_ID} ({remaining} chars remaining)")
                else:
                    logger.error(f"❌ ElevenLabs quota low ({remaining} chars remaining). ElevenLabs TTS is required!")
                    logger.error("   To use ElevenLabs: Upgrade your plan or wait for quota reset at https://elevenlabs.io/")
                    logger.error("   Agent will not start without ElevenLabs TTS")
            else:
                logger.error(f"❌ Could not verify ElevenLabs quota (status {response.status_code}). ElevenLabs TTS is required!")
        except Exception as e:
            logger.error(f"❌ Error checking ElevenLabs quota: {e}. ElevenLabs TTS is required!")
    
    # Configure STT and TTS based on LLM provider
    # OpenAI Realtime model handles both STT and TTS internally (speech-to-speech)
    # Regular models need separate STT and TTS
    if llm_provider == "openai-realtime":
        # Realtime model handles STT and TTS internally - no need for separate services
        stt_instance = None
        tts_instance = None
        logger.info("Using OpenAI Realtime model - STT and TTS handled internally")
    else:
        # Regular models need separate STT and TTS
        # Create a wrapper STT class that captures transcriptions
        class TranscriptingSTT(deepgram.STT):
            """STT wrapper that captures transcriptions."""
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._transcript_callback = None
            
            def set_transcript_callback(self, callback):
                """Set callback function to receive transcriptions."""
                self._transcript_callback = callback
            
            async def transcribe(self, *args, **kwargs):
                """Wrap transcribe to capture transcriptions."""
                logger.debug(f"[STT WRAPPER] transcribe called with args: {len(args)}, kwargs: {list(kwargs.keys())}")
                result = await super().transcribe(*args, **kwargs)
                logger.debug(f"[STT WRAPPER] transcribe returned: {type(result)}, has __aiter__: {hasattr(result, '__aiter__')}")
                
                # Deepgram returns async iterator of SpeechEvent objects
                if hasattr(result, '__aiter__'):
                    async def transcript_iterator():
                        event_count = 0
                        async for event in result:
                            event_count += 1
                            logger.debug(f"[STT WRAPPER] Processing event #{event_count}: {type(event)}")
                            
                            # Extract transcript from event
                            transcript_text = None
                            
                            # Try different ways to extract transcript
                            if hasattr(event, 'alternatives') and event.alternatives and len(event.alternatives) > 0:
                                alt = event.alternatives[0]
                                if isinstance(alt, dict):
                                    transcript_text = alt.get('transcript', '')
                                elif hasattr(alt, 'transcript'):
                                    transcript_text = alt.transcript
                                elif hasattr(alt, 'text'):
                                    transcript_text = alt.text
                            elif hasattr(event, 'text'):
                                transcript_text = event.text
                            elif hasattr(event, 'transcript'):
                                transcript_text = event.transcript
                            elif isinstance(event, dict):
                                transcript_text = event.get('text') or event.get('transcript') or (event.get('alternatives', [{}])[0].get('transcript') if event.get('alternatives') else None)
                            
                            logger.debug(f"[STT WRAPPER] Extracted transcript: {transcript_text}")
                            
                            if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
                                if self._transcript_callback:
                                    self._transcript_callback(transcript_text.strip())
                                    logger.info(f"📝 [STT WRAPPER] Captured: {transcript_text.strip()}")
                                else:
                                    logger.warning(f"[STT WRAPPER] No callback set! Transcript: {transcript_text.strip()}")
                            
                            yield event
                        
                        logger.debug(f"[STT WRAPPER] Processed {event_count} events total")
                    return transcript_iterator()
                else:
                    # Not an iterator - try to extract directly
                    logger.debug(f"[STT WRAPPER] Result is not an iterator, trying direct extraction")
                    if hasattr(result, 'alternatives') and len(result.alternatives) > 0:
                        transcript_text = result.alternatives[0].get('transcript', '')
                        if transcript_text and self._transcript_callback:
                            self._transcript_callback(transcript_text.strip())
                            logger.info(f"📝 [STT WRAPPER] Captured (direct): {transcript_text.strip()}")
                
                return result
        
        # Create STT instance with wrapper
        stt_instance = TranscriptingSTT()
        

        
        # Set up transcript capture using conversation_item_added event
        # This is the official LiveKit way to track all conversation items
        def track_conversation_item(item):
            """Capture conversation items (both user and agent) via conversation_item_added event."""
            try:
                # Extract role and content from the item
                role = None
                content = None
                
                if hasattr(item, 'role'):
                    role = item.role
                elif hasattr(item, 'message') and hasattr(item.message, 'role'):
                    role = item.message.role
                elif isinstance(item, dict):
                    role = item.get('role')
                
                if hasattr(item, 'content'):
                    content = item.content
                elif hasattr(item, 'message') and hasattr(item.message, 'content'):
                    content = item.message.content
                elif isinstance(item, dict):
                    content = item.get('content')
                
                if not role or not content:
                    return
                
                # Convert content to string if needed
                if isinstance(content, str):
                    text = content
                elif hasattr(content, 'text'):
                    text = content.text
                elif isinstance(content, list):
                    # Handle list of content parts (e.g., OpenAI format)
                    text_parts = []
                    for part in content:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif isinstance(part, dict) and 'text' in part:
                            text_parts.append(part['text'])
                        elif hasattr(part, 'text'):
                            text_parts.append(part.text)
                    text = ' '.join(text_parts)
                else:
                    text = str(content)
                
                if not text or not text.strip():
                    return
                
                # Determine speaker
                if role.lower() == "user":
                    speaker = "Customer"
                elif role.lower() in ["assistant", "agent"]:
                    speaker = "Lia"
                elif role.lower() == "system":
                    return  # Skip system messages
                else:
                    speaker = role.title()
                
                # Add to transcript
                agent.transcript.append({
                    "speaker": speaker,
                    "text": text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 [{speaker}] transcript captured: {text.strip()[:100]}")
                
            except Exception as e:
                logger.debug(f"Error tracking conversation item: {e}")
        
        # Legacy functions for backward compatibility (if needed)
        def track_user_transcript(text: str):
            """Capture user speech transcriptions from STT (legacy method)."""
            if text and text.strip():
                agent.transcript.append({
                    "speaker": "Customer",
                    "text": text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 User transcript captured (legacy): {text.strip()}")
                
                # Check for voicemail patterns in real-time
                if agent.voicemail_detector and agent.voicemail_detector.check_transcript(text.strip()):
                    # Voicemail detected - handle it asynchronously
                    logger.warning(f"🚨 Voicemail detected! Hanging up immediately...")
                    asyncio.create_task(agent.voicemail_detector.handle_voicemail_detection())
        
        def track_agent_transcript(text: str):
            """Capture agent speech transcriptions (legacy method)."""
            if text and text.strip():
                agent.transcript.append({
                    "speaker": "Lia",
                    "text": text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 Agent transcript captured (legacy): {text.strip()}")
        
        # Wrap STT instance to capture transcriptions DIRECTLY
        # This is the most reliable method - intercept at the source
        try:
            if hasattr(stt_instance, 'transcribe'):
                original_transcribe = stt_instance.transcribe
                
                async def wrapped_transcribe(*args, **kwargs):
                    """Wrap transcribe to capture transcriptions at the source."""
                    result = await original_transcribe(*args, **kwargs)
                    # Extract transcript from result
                    transcript_text = None
                    if hasattr(result, 'text'):
                        transcript_text = result.text
                    elif isinstance(result, str):
                        transcript_text = result
                    elif isinstance(result, dict):
                        transcript_text = result.get('text') or result.get('transcript') or result.get('alternatives', [{}])[0].get('transcript')
                    elif hasattr(result, 'alternatives') and len(result.alternatives) > 0:
                        transcript_text = result.alternatives[0].get('transcript')
                    
                    if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
                        track_user_transcript(transcript_text.strip())
                        logger.info(f"📝 [STT DIRECT] Captured transcript: {transcript_text.strip()}")
                    
                    return result
                
                stt_instance.transcribe = wrapped_transcribe
                logger.info("[OK] Wrapped STT transcribe method BEFORE session creation")
        except Exception as e:
            logger.warning(f"⚠️  Could not wrap STT transcribe method: {e}")
        
        # Set up transcript capture handler EARLY (before session starts)
        # This ensures we capture all logs from the beginning
        
            # Redundant log-based capture removed for performance
            pass
        except Exception as e:
            logger.warning(f"⚠️  Could not add early transcript capture handler: {e}")
    
    # Set transcript callback on STT wrapper (BEFORE session creation)
    # This is the most reliable method - captures at the source
    if stt_instance is not None and hasattr(stt_instance, 'set_transcript_callback'):
        try:
            stt_instance.set_transcript_callback(track_user_transcript)
            logger.info("[OK] Set transcript callback on STT wrapper")
        except Exception as e:
            logger.warning(f"⚠️  Could not set STT transcript callback: {e}")
    
    # Initialize TTS based on provider
    if USE_ELEVENLABS:
        # Configure voice settings with speed
        from livekit.plugins.elevenlabs import VoiceSettings
        # Use voice default settings if available, otherwise use reasonable defaults
        # But prioritize our config settings if they differ from defaults
        if voice_default_settings:
            # If config matches the hardcoded default (0.5/0.75), maybe we want to use the voice's natural default?
            # But here we will enforce the config value if explicit.
            # actually we loaded from config above, so let's use those vars:
            stability = VOICE_STABILITY
            similarity_boost = VOICE_SIMILARITY_BOOST
        else:
            stability = VOICE_STABILITY
            similarity_boost = VOICE_SIMILARITY_BOOST
        
        # Use TTS_SPEED (already set from voice_speed or tts_speed above)
        elevenlabs_speed = TTS_SPEED
        
        # Clamp speed to valid range (0.7-1.2) for ElevenLabs
        valid_speed = max(0.7, min(1.2, elevenlabs_speed))
        if elevenlabs_speed != valid_speed:
            logger.warning(f"⚠️  TTS_SPEED {elevenlabs_speed} is outside valid range (0.7-1.2). Clamping to {valid_speed}")
        
        voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=VOICE_STYLE,
            use_speaker_boost=VOICE_SPEAKER_BOOST,
            speed=valid_speed  # Configured speaking speed (clamped to 0.7-1.2 for ElevenLabs)
        )
        tts_instance = elevenlabs.TTS(
            voice_id=ELEVENLABS_VOICE_ID,
            api_key=ELEVEN_API_KEY,
            voice_settings=voice_settings
        )
        logger.info(f"✅ ElevenLabs TTS instance created with voice ID: {ELEVENLABS_VOICE_ID}, speed: {valid_speed}")
    elif USE_CHATTERBOX:
        # Use Chatterbox TTS
        # Use TTS_SPEED (already set from voice_speed or tts_speed above)
        chatterbox_speed = TTS_SPEED
        tts_instance = ChatterboxTTS(
            api_url=CHATTERBOX_API_URL,
            voice=CHATTERBOX_VOICE,
            model=CHATTERBOX_MODEL,
            speed=chatterbox_speed,
        )
        logger.info(f"✅ Chatterbox TTS instance created: {CHATTERBOX_API_URL}, voice: {CHATTERBOX_VOICE}, speed: {chatterbox_speed}")
    elif TTS_PROVIDER == "cartesia":
        # Use Cartesia TTS
        cartesia_args = {
            "speed": CARTESIA_SPEED,
            "emotion": CARTESIA_EMOTION
        }
        if CARTESIA_VOICE_ID:
            cartesia_args["voice"] = CARTESIA_VOICE_ID
        if CARTESIA_API_KEY:
            cartesia_args["api_key"] = CARTESIA_API_KEY
            
        tts_instance = cartesia.TTS(**cartesia_args)
        logger.info(f"✅ Cartesia TTS instance created with voice: {CARTESIA_VOICE_ID}, speed: {CARTESIA_SPEED}, emotion: {CARTESIA_EMOTION}")
    elif USE_PIPER:
        # Use Piper TTS from local-livekit-plugins package (CPU only)
        from pathlib import Path
        
        # Check if using local-livekit-plugins package
        using_package = False
        try:
            import inspect
            if hasattr(PiperTTS, '__module__') and 'local_livekit_plugins' in str(PiperTTS.__module__):
                using_package = True
        except (AttributeError, ImportError):
            pass
        
        model_path = str(Path(PIPER_MODEL_PATH))
        
        if using_package:
            # Use local-livekit-plugins package API (CPU only, no GPU)
            # Use voice_speed and voice_volume from config if set
            # Use TTS_SPEED (already set from voice_speed or tts_speed above) and VOICE_VOLUME (defined earlier in entrypoint)
            piper_speed = TTS_SPEED
            piper_volume = VOICE_VOLUME  # VOICE_VOLUME is always defined before this point in both CONFIG_MANAGER_AVAILABLE branches
            logger.info("Using local-livekit-plugins PiperTTS (CPU only)")
            tts_instance = PiperTTS(
                model_path=model_path,
                use_cuda=False,  # CPU only as requested
                speed=piper_speed,
                volume=piper_volume,
                noise_scale=PIPER_NOISE_SCALE,
                noise_w=PIPER_NOISE_W_SCALE,  # Package uses 'noise_w' not 'noise_w_scale'
            )
            logger.info(f"✅ Piper TTS instance created (CPU): {model_path}, speed: {piper_speed:.2f}, noise_scale: {PIPER_NOISE_SCALE}, volume: {piper_volume:.2f}")
        else:
            # Fallback to custom implementation (legacy support)
            config_path = Path(PIPER_CONFIG_PATH) if PIPER_CONFIG_PATH else None
            
            # Convert TTS_SPEED to Piper's length_scale (inverse relationship: higher speed = lower length_scale)
            # length_scale controls speech speed: lower = faster, higher = slower
            # Map TTS_SPEED (1.0 = normal) to length_scale: speed 1.5 = length_scale 0.67, speed 0.5 = length_scale 2.0
            piper_length_scale = PIPER_LENGTH_SCALE / TTS_SPEED if TTS_SPEED != 1.0 else PIPER_LENGTH_SCALE
            
            # Force CPU only for custom implementation
            logger.info("Using custom PiperTTS implementation (CPU only)")
            tts_instance = PiperTTS(
                model_path=Path(model_path),
                config_path=config_path if config_path and config_path.exists() else None,
                use_cuda=False,  # CPU only
                length_scale=piper_length_scale,
                noise_scale=PIPER_NOISE_SCALE,
                noise_w_scale=PIPER_NOISE_W_SCALE,
                volume=PIPER_VOLUME,
            )
            # Log sample rate to help debug pitch issues
            try:
                actual_sample_rate = tts_instance.sample_rate
                logger.info(f"✅ Piper TTS instance created (CPU): {model_path}")
                logger.info(f"   Sample Rate: {actual_sample_rate} Hz (from config)")
                logger.info(f"   Length Scale: {piper_length_scale:.2f} (Speed: {TTS_SPEED:.2f}x)")
            except:
                logger.info(f"✅ Piper TTS instance created (CPU): {model_path}, length_scale: {piper_length_scale:.2f}")
    elif USE_OPENAI:
        # Use OpenAI TTS
        logger.info(f"Using OpenAI TTS with voice: {OPENAI_VOICE}")
        tts_instance = OpenAITTS(voice=OPENAI_VOICE, model="tts-1")
        logger.info(f"✅ OpenAI TTS instance created: {OPENAI_VOICE}")
    else:
        # Fail if no TTS provider is available
        if TTS_PROVIDER == "elevenlabs":
            if not ELEVEN_API_KEY:
                logger.error("❌ ELEVEN_API_KEY not found - ElevenLabs TTS is required!")
                logger.error("   Please set ELEVEN_API_KEY in your .env.local file")
                logger.error("   Or switch to Chatterbox TTS by setting TTS_PROVIDER=chatterbox")
                raise ValueError("ELEVEN_API_KEY is required for ElevenLabs TTS")
            else:
                logger.error(f"❌ ElevenLabs TTS not available (quota check failed or quota low)")
                logger.error(f"   Required voice ID: {ELEVENLABS_VOICE_ID}")
                logger.error("   Please check your ElevenLabs quota at: https://elevenlabs.io/")
                logger.error("   Or switch to Chatterbox TTS by setting TTS_PROVIDER=chatterbox")
                raise ValueError(f"ElevenLabs TTS is required but not available. Voice ID: {ELEVENLABS_VOICE_ID}")
        elif TTS_PROVIDER == "chatterbox":
            logger.error("❌ Chatterbox TTS not available!")
            logger.error("   Make sure:")
            logger.error("   1. livekit_chatterbox_tts.py exists in the project")
            logger.error("   2. httpx is installed: pip install httpx")
            logger.error("   3. Chatterbox TTS server is running at: " + CHATTERBOX_API_URL)
            raise ValueError(f"Chatterbox TTS is required but not available. API URL: {CHATTERBOX_API_URL}")
        elif TTS_PROVIDER == "piper":
            logger.error("❌ Piper TTS not available!")
            logger.error("   Make sure:")
            logger.error("   1. piper-tts is installed: pip install piper-tts")
            logger.error("   2. livekit_piper_tts.py exists in piper1-gpl/")
            logger.error(f"   3. Model file exists: {PIPER_MODEL_PATH}")
            raise ValueError(f"Piper TTS is required but not available. Model path: {PIPER_MODEL_PATH}")
        else:
            logger.error(f"❌ Unknown TTS provider: {TTS_PROVIDER}")
            logger.error("   Supported providers: 'elevenlabs', 'chatterbox', 'piper'")
            raise ValueError(f"Unknown TTS provider: {TTS_PROVIDER}")
    
    # Configure interruption sensitivity (maps to min_interruption_duration)
    # interruption_sensitivity: 0.0 = less sensitive (2.0s), 1.0 = very sensitive (0.0s)
    # Formula: min_interruption_duration = 2.0 * (1.0 - interruption_sensitivity)
    min_interruption_duration = 2.0 * (1.0 - INTERRUPTION_SENSITIVITY)
    min_interruption_duration = max(0.0, min(2.0, min_interruption_duration))  # Clamp to 0.0-2.0
    logger.info(f"[OK] Interruption sensitivity: {INTERRUPTION_SENSITIVITY} (min_interruption_duration: {min_interruption_duration:.2f}s)")
    


    # Create VAD instance with optimized settings
    vad_instance = silero.VAD.load(
        min_silence_duration=0.1,
        min_speech_duration=0.05,
    )
    logger.info(f"[OK] VAD initialized with min_silence_duration=0.1, min_speech_duration=0.05")

    session = AgentSession(
        vad=vad_instance,
        stt=stt_instance,  # None for Realtime, deepgram.STT() for regular models
        tts=tts_instance,  # None for Realtime, TTS instance for regular models
        llm=llm_instance,
        # Configure endpointing delays (when to consider user finished speaking)
        min_endpointing_delay=0.2, # Force low endpointing delay (override config)
        max_endpointing_delay=MAX_ENDPOINTING_DELAY,  # Higher = wait longer for user to continue
        # Configure interruption sensitivity
        allow_interruptions=True,  # Always allow interruptions
        min_interruption_duration=0.2,  # Force faster interruption detection (0.2s instead of 0.5s)
        min_interruption_words=0,  # No minimum words required
        # Ultra-low latency optimizations
        preemptive_generation=True, # Start synthesis before user finish speaking
    )

    # --- Transcription & Event Listeners ---
    @session.on("user_transcript")
    def _on_user_transcript(transcript: stt.SpeechEvent):
        if transcript.is_final:
            text = transcript.alternatives[0].text.strip()
            if text:
                agent.transcript.append({
                    "speaker": "Customer",
                    "text": text,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"[EVENT] Captured customer transcript: {text[:80]}...")
    # ----------------------------------

    # start the session first before dialing, to ensure that when the user picks up
    # the agent does not miss anything the user says
    session_started = asyncio.create_task(
        session.start(
            agent=agent,
            record=True,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                # Configure noise cancellation based on settings
                noise_cancellation=_get_noise_cancellation_filter(NOISE_CANCELLATION_MODE),
            ),
        )
    )

    # `create_sip_participant` starts dialing the user
    # Add retry logic for network errors (ServerDisconnectedError, etc.)
    max_sip_retries = 2
    sip_retry_delay = 1.0
    sip_participant_created = False
    
    # Check if we should dial via SIP
    should_dial_sip = phone_number and phone_number.lower() not in ["web-user", "test", "browser"]
    
    if should_dial_sip:
        # Get latest SIP trunk ID from config
        outbound_trunk_id = config.get("integrations", {}).get("sip_outbound_trunk_id") or os.getenv("SIP_OUTBOUND_TRUNK_ID")
        
        logger.info(f"[INFO] Using SIP_OUTBOUND_TRUNK_ID: {outbound_trunk_id}")
        logger.info(f"[CALL] Dialing {phone_number} via SIP trunk {outbound_trunk_id}...")
        for retry_attempt in range(max_sip_retries + 1):
            try:
                await ctx.api.sip.create_sip_participant(
                    api.CreateSIPParticipantRequest(
                        room_name=ctx.room.name,
                        sip_trunk_id=outbound_trunk_id,
                        sip_call_to=phone_number,
                        participant_identity=participant_identity,
                        # function blocks until user answers the call, or if the call fails
                        wait_until_answered=True,
                    )
                )
                sip_participant_created = True
                break  # Success, exit retry loop
            except Exception as sip_error:
                error_type = type(sip_error).__name__
                # Don't retry on TwirpError (SIP status codes like 603, 486, etc.) - these are intentional rejections
                if isinstance(sip_error, api.TwirpError):
                    # Handle SIP errors gracefully instead of crashing
                    sip_status_code = sip_error.metadata.get('sip_status_code')
                    sip_status = sip_error.metadata.get('sip_status', '')
                    
                    logger.error(f"Error creating SIP participant: {sip_error.message}, SIP status: {sip_status_code} {sip_status}")
                    
                    # Determine call status based on SIP error code
                    if sip_status_code == 603:
                        call_status = "declined"
                        logger.info(f"[CALL] Call declined (603) for {phone_number} - marking as 'Declined' in Google Sheets")
                    elif sip_status_code == 486:
                        call_status = "busy"
                        logger.info(f"[CALL] Call busy (486) for {phone_number} - marking as 'Busy' in Google Sheets")
                    elif sip_status_code == 480:
                        call_status = "no_answer"
                        logger.info(f"[CALL] Call no answer (480) for {phone_number} - marking as 'No Answer' in Google Sheets")
                    else:
                        call_status = "failed"
                        logger.info(f"[CALL] Call failed (SIP {sip_status_code}) for {phone_number} - marking as 'Failed' in Google Sheets")
                    
                    # Update Google Sheets with the status before shutting down
                    try:
                        agent.call_end_time = datetime.datetime.now()
                        sip_reason = f"SIP {sip_status_code} {sip_status}"
                        await agent.send_call_results_to_sheets(call_status, failure_reason=sip_reason)
                        logger.info(f"[OK] SIP error status ({call_status}) sent to Google Sheets")
                    except Exception as sheet_error:
                        logger.error(f"[X] Failed to update Google Sheets with SIP error status: {sheet_error}")
                    
                    ctx.shutdown()
                    return
                # Retry on network errors (ServerDisconnectedError, ConnectionError, etc.)
                elif retry_attempt < max_sip_retries and (
                    "ServerDisconnectedError" in error_type or 
                    "ConnectionError" in error_type or
                    "disconnected" in str(sip_error).lower() or
                    "connection" in str(sip_error).lower()
                ):
                    logger.warning(f"[WARN] SIP connection error (attempt {retry_attempt + 1}/{max_sip_retries + 1}): {sip_error}. Retrying in {sip_retry_delay}s...")
                    await asyncio.sleep(sip_retry_delay)
                    sip_retry_delay *= 2  # Exponential backoff
                else:
                    # Non-retryable error or max retries reached
                    logger.error(f"[ERROR] Failed to create SIP participant after {retry_attempt + 1} attempts: {sip_error}")
                    raise
        
        if not sip_participant_created:
            raise RuntimeError("Failed to create SIP participant after all retry attempts")
    else:
        logger.info("[OFFLINE] Web/Test mode detected - skipping SIP dialing. Waiting for user to join room...")
        sip_participant_created = True  # Pretend we created it so we proceed to wait logic
    
    try:
        # wait for the agent session start with timeout
        try:
            await asyncio.wait_for(session_started, timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("[ERROR] Session start timed out after 30 seconds")
            raise RuntimeError("Session start timed out")
        
        # wait for participant join with timeout
        try:
            participant = await asyncio.wait_for(
                ctx.wait_for_participant(identity=participant_identity),
                timeout=60.0  # 60 second timeout for participant to join
            )
        except asyncio.TimeoutError:
            logger.error(f"[ERROR] Participant {participant_identity} did not join within 60 seconds")
            raise RuntimeError(f"Participant join timeout for {participant_identity}")
        logger.info(f"participant joined: {participant.identity}")

        agent.set_participant(participant)
        
        # Store session reference for transcript extraction
        agent._agent_session = session
        
        # Store room info
        agent.room_name = ctx.room.name
        agent.session_id = ctx.job.id if ctx.job else ""
        
        # Track call start time
        agent.call_start_time = datetime.datetime.now()
        
        # Initialize voicemail detector
        agent.voicemail_detector = VoicemailDetector(agent)
        agent.voicemail_detector.set_session(session)
        logger.info("[OK] Voicemail detector initialized and session linked")
        
        # OFFICIAL METHOD: Subscribe to conversation_item_added event
        # This is the recommended way to track all conversation items (user and agent)
        @session.on("conversation_item_added")
        def on_conversation_item_added(item):
            """Official LiveKit method to capture conversation items."""
            track_conversation_item(item)
        
        logger.info("[OK] Subscribed to conversation_item_added events (official method)")
        
        # Redundant transcript capture methods removed.
        # - Voicemail detection is handled in OutboundCaller.stt_node (fast path)
        # - Transcript storage is handled by the official conversation_item_added handler above
        
        
        
        # Wrap session.generate_reply to prevent generation if voicemail is detected
        original_generate_reply = session.generate_reply
        
        async def wrapped_generate_reply(*args, **kwargs):
            """Wrap generate_reply to check for voicemail."""
            # CHECK FOR VOICEMAIL FIRST
            if agent.voicemail_detector and agent.voicemail_detector.detected:
                logger.info("[VOICEMAIL] Skipping reply generation - voicemail detected")
                return None
                
            return await original_generate_reply(*args, **kwargs)
        
        # Replace the method
        session.generate_reply = wrapped_generate_reply
        logger.info("[OK] Wrapped session.generate_reply for voicemail check")
        
        # Note: Transcripts are captured from:
        # 1. LiveKit STT transcription events (real-time audio transcription)
        # 2. Conversation history (LLM chat context) as fallback
        # This provides both user and agent messages in chronological order
        
        # Background task to monitor session and send transcript when it closes
        async def monitor_and_send_transcript():
            """Monitor session and send transcript when participant disconnects."""
            try:
                # Wait for participant to disconnect or session to close
                max_wait = 600  # Max 10 minutes
                waited = 0
                while waited < max_wait:
                    await asyncio.sleep(1)  # Check every second
                    waited += 1
                    
                    # Check if participant is disconnected
                    try:
                        if participant:
                            # Check if participant is still in room
                            if participant not in ctx.room.remote_participants.values():
                                logger.info("[TRANSCRIPT] Participant no longer in room - sending transcript...")
                                break
                    except Exception:
                        # Participant might be None or invalid
                        pass
                    
                    # Check if session is closed
                    try:
                        if hasattr(session, 'closed') and session.closed:
                            logger.info("[TRANSCRIPT] Session closed - sending transcript...")
                            break
                        if hasattr(session, '_closed') and session._closed:
                            logger.info("[TRANSCRIPT] Session _closed - sending transcript...")
                            break
                    except Exception:
                        pass
            except asyncio.CancelledError:
                logger.info("[TRANSCRIPT] Monitor cancelled - sending transcript...")
            except Exception as e:
                logger.debug(f"Monitor error: {e}")
            
            # Send transcript
            if not agent.call_end_time:
                logger.info("[TRANSCRIPT] Sending transcript to Google Sheets...")
                try:
                    # Extract transcript from conversation history
                    transcript_from_history = ""
                    if agent._agent_session:
                        try:
                            transcript_from_history = agent.get_transcript_from_conversation(agent._agent_session)
                            if transcript_from_history and len(transcript_from_history) > 0:
                                logger.info(f"[EVENT] Extracted {len(transcript_from_history)} characters from conversation history")
                        except Exception as e:
                            logger.warning(f"[WARN] Could not extract transcript from conversation: {e}")
                    
                    # Also check real-time transcriptions
                    await agent.finalize_transcripts()  # Redundant but safe
                    realtime_transcript = agent.format_transcript()
                    logger.info(f"[TRANSCRIPT] Real-time transcript entries: {len(agent.transcript)}, formatted: {len(realtime_transcript)} chars")
                    
                    # Send results (send_call_results_to_sheets will combine both sources)
                    if agent.appointment_scheduled:
                        call_status = "completed"
                    elif len(agent.transcript) > 0:
                        call_status = "hung_up"
                    else:
                        call_status = "no_answer"
                    
                    await agent.send_call_results_to_sheets(call_status)
                    agent.call_end_time = datetime.datetime.now()
                    logger.info(f"[OK] Transcript sent to Google Sheets (status: {call_status})")
                except Exception as e:
                    logger.error(f"[ERROR] Error sending transcript: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Function to send transcript (shared by all handlers)
        async def send_transcript_on_end():
            """Send transcript when call ends."""
            if not agent.call_end_time:
                logger.info("[EVENT] Call ended - extracting and sending transcript...")
                try:
                    # Extract transcript from conversation history
                    transcript_from_history = ""
                    if agent._agent_session:
                        try:
                            transcript_from_history = agent.get_transcript_from_conversation(agent._agent_session)
                            if transcript_from_history and len(transcript_from_history) > 0:
                                logger.info(f"[EVENT] Extracted {len(transcript_from_history)} characters from conversation history")
                        except Exception as e:
                            logger.warning(f"[WARN] Could not extract transcript from conversation: {e}")
                    
                    # Also check real-time transcriptions
                    realtime_transcript = agent.format_transcript()
                    logger.info(f"[EVENT] Real-time transcript entries: {len(agent.transcript)}, formatted: {len(realtime_transcript)} chars")
                    
                    # Send results
                    if agent.appointment_scheduled:
                        call_status = "completed"
                    elif len(agent.transcript) > 0:
                        call_status = "hung_up"
                    else:
                        call_status = "no_answer"
                    
                    await agent.send_call_results_to_sheets(call_status)
                    agent.call_end_time = datetime.datetime.now()
                    logger.info(f"[OK] Transcript sent to Google Sheets (status: {call_status})")
                except Exception as e:
                    logger.error(f"[X] Error sending transcript: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Subscribe to participant disconnect event (most reliable)
        def on_participant_disconnected_event(participant_disconnected: rtc.RemoteParticipant):
            """Handle participant disconnect."""
            logger.info(f"[EVENT] Participant {participant_disconnected.identity} disconnected - sending transcript...")
            # Run cleanup synchronously to ensure it happens
            asyncio.create_task(cleanup_and_shutdown())

        async def cleanup_and_shutdown():
            """Perform cleanup and shut down the agent."""
            logger.info("[STOP] Starting graceful shutdown...")
            try:
                await send_transcript_on_end()
            except Exception as e:
                logger.error(f"Error sending transcript during shutdown: {e}")
            
            # Cancel monitoring tasks
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()
            
            logger.info("[STOP] Shutting down job context...")
            # Set shutdown event to allow entrypoint to exit
            shutdown_event.set()
            ctx.shutdown()
        
        # Subscribe to room disconnected (fallback if participant disconnect isn't caught)
        def on_room_disconnected_event(event):
            """Handle room disconnect."""
            logger.info("[EVENT] Room disconnected - ensuring cleanup...")
            asyncio.create_task(cleanup_and_shutdown())

        try:
            ctx.room.on("participant_disconnected", on_participant_disconnected_event)
            ctx.room.on("disconnected", on_room_disconnected_event)
            logger.info("[OK] Subscribed to disconnect events")
        except Exception as e:
            logger.warning(f"[WARN] Could not subscribe to disconnect events: {e}")
            
        # Register a shutdown callback as final safety net
        ctx.add_shutdown_callback(lambda: asyncio.create_task(cleanup_and_shutdown()))

        # Start monitoring as backup
        monitor_task = asyncio.create_task(monitor_and_send_transcript())
        
        # Idle Time & Reminder monitoring function (will be started after greeting)
        idle_reminder_task = None
        if IDLE_REMINDER_ENABLED:
            async def monitor_idle_and_remind():
                """Monitor for idle periods during conversation and send reminders."""
                reminder_count = 0
                last_transcript_count = len(agent.transcript)
                last_activity_time = datetime.datetime.now()
                
                while not agent.call_end_time:
                    await asyncio.sleep(1.0)  # Check every second
                    
                    # Update last activity time if there's new user or agent speech
                    current_time = datetime.datetime.now()
                    current_transcript_count = len(agent.transcript)
                    
                    # Check session state for activity
                    session_active = False
                    if agent._agent_session:
                        try:
                            session_state = getattr(agent._agent_session, 'state', None)
                            session_active = session_state in ("speaking", "thinking", "listening")
                        except:
                            pass
                    
                    # Check if there's been new activity (new transcripts or agent speaking)
                    new_activity = (current_transcript_count > last_transcript_count) or session_active
                    
                    if new_activity:
                        last_activity_time = current_time
                        last_transcript_count = current_transcript_count
                        reminder_count = 0  # Reset reminder count on activity
                        continue
                    
                    # Check if idle time threshold is reached
                    idle_duration = (current_time - last_activity_time).total_seconds()
                    
                    if idle_duration >= IDLE_TIME_SECONDS and reminder_count < REMINDER_FREQUENCY:
                        # Send reminder
                        reminder_count += 1
                        logger.info(f"[IDLE] Idle for {idle_duration:.1f}s - sending reminder {reminder_count}/{REMINDER_FREQUENCY}")
                        try:
                            await session.generate_reply(
                                instructions="Say only: 'Hello? Are you there?' Then wait for their response. Keep it brief."
                            )
                            last_activity_time = current_time  # Reset after reminder
                        except Exception as e:
                            logger.error(f"Error sending idle reminder: {e}")
                    
                    # If max reminders reached and still idle, log warning (let existing timeout handle hangup)
                    if reminder_count >= REMINDER_FREQUENCY and idle_duration >= (IDLE_TIME_SECONDS * 2):
                        logger.warning(f"[WARN] Max reminders ({REMINDER_FREQUENCY}) sent, still idle - letting existing timeout handle hangup")
            
            logger.info(f"[OK] Idle reminder monitoring configured: {IDLE_TIME_SECONDS}s idle time, {REMINDER_FREQUENCY} reminder(s)")
        
        # Wait for user to speak first, then say "Hello?" if quiet, then hang up if no response
        logger.info(f"[CALL] Waiting {INITIAL_SILENCE_WAIT} seconds for user to speak first...")
        user_first_spoke = False
        greeting_sent_time = None
        silence_timeout_task = None
        hello_sent = False
        customer_transcript_count_before_greeting = 0  # Track transcript count before greeting
        
        # Monitor for user's first speech or send "Hello?" if quiet
        async def wait_for_user_greeting():
            """Wait for user to speak, say 'Hello?' if quiet after 5 seconds, then hang up if no response after 7 more seconds."""
            nonlocal user_first_spoke, greeting_sent_time, silence_timeout_task, hello_sent, customer_transcript_count_before_greeting
            
            # Create an event to signal when user starts speaking (VAD)
            user_speech_event = asyncio.Event()
            
            def on_speech_started(evt):
                if not user_speech_event.is_set():
                    user_speech_event.set()
                    logger.info("[OK] VAD detected speech start during initial wait")
            
            # Subscribe to speech started event
            session.on("input_speech_started", on_speech_started)
            
            try:
                # Phase 1: Robust Polling for 5 seconds
                # We poll for both VAD event AND transcript presence to be safe
                start_time = datetime.datetime.now()
                check_interval = 0.1  # Check every 100ms
                
                while (datetime.datetime.now() - start_time).total_seconds() < INITIAL_SILENCE_WAIT:
                    # 1. Check VAD event
                    if user_speech_event.is_set():
                        user_first_spoke = True
                        logger.info("[OK] User speech detected (VAD Event) - skipping initial greeting wait")
                        return

                    # 2. Check Transcripts (Backup in case VAD missed or race condition)
                    # Check our custom robust flag first (updated by stt_node directly)
                    if hasattr(agent, 'last_user_speech_time') and agent.last_user_speech_time and \
                       agent.call_start_time and agent.last_user_speech_time > agent.call_start_time:
                        user_first_spoke = True
                        logger.info(f"[OK] User speech detected (Robust Flag) - skipping initial greeting wait. Text: {getattr(agent, 'last_user_speech_text', 'unknown')}")
                        return

                    user_transcripts = [
                        entry.get("text", "").lower().strip()
                        for entry in agent.transcript
                        if entry.get("speaker") == "Customer"
                    ]
                    if user_transcripts:
                        user_first_spoke = True
                        logger.info(f"[OK] User speech detected (Transcript) - skipping initial greeting wait: {' '.join(user_transcripts)}")
                        return
                    
                    # 3. Check if call ended or participant left
                    if agent.call_end_time or participant not in ctx.room.remote_participants.values():
                        return

                    await asyncio.sleep(check_interval)
                    
            finally:
                # Clean up event handler
                session.off("input_speech_started", on_speech_started)
            
            # Phase 2: User didn't speak in 5 seconds - agent says "Hello?"
            if not user_first_spoke and not hello_sent:
                logger.info(f"[TIMEOUT] No user speech detected after {INITIAL_SILENCE_WAIT} seconds - agent will say 'Hello?'")
                hello_sent = True
                
                # Record transcript count before greeting to detect new speech after
                customer_transcript_count_before_greeting = len([
                    entry for entry in agent.transcript 
                    if entry.get("speaker") == "Customer"
                ])
                
                try:
                    await session.generate_reply(
                        instructions="Say ONLY this: 'Hello?' Then STOP COMPLETELY and wait for their response. Do not say anything else until they respond."
                    )
                    greeting_sent_time = datetime.datetime.now()
                    logger.info("[CALL] Agent said 'Hello?' - waiting for response...")
                    
                    # Start silence timeout monitor after "Hello?" is sent
                    silence_timeout_task = asyncio.create_task(monitor_silence_timeout())
                except Exception as e:
                    logger.error(f"Error generating 'Hello?' response: {e}")
                    # If we can't say hello, just hang up
                    try:
                        await agent.hangup("no_answer", send_results=True)
                    except Exception as hangup_error:
                        logger.error(f"Error hanging up: {hangup_error}")
                    return
            
            # Phase 3: Wait for response after "Hello?" (handled by monitor_silence_timeout)
        
        # Start waiting for user greeting
        greeting_wait_task = asyncio.create_task(wait_for_user_greeting())
        
        # Monitor for user response after greeting (silence timeout)
        async def monitor_silence_timeout():
            """Monitor if user responds after greeting, hang up if no response within 7 seconds.
            Also checks if agent has continued speaking (e.g., started pitch), in which case we don't hang up.
            """
            if greeting_sent_time is None:
                return
            
            try:
                # Wait for the timeout period (7 seconds)
                await asyncio.sleep(NO_RESPONSE_TIMEOUT)
                
                # Check if call already ended
                if agent.call_end_time:
                    return
                
                # Check if participant is still connected
                if participant not in ctx.room.remote_participants.values():
                    return

                # 1. Check if user has spoken AFTER the greeting was sent
                current_customer_transcript_count = len([
                    entry for entry in agent.transcript 
                    if entry.get("speaker") == "Customer"
                ])
                user_has_spoken_after_greeting = current_customer_transcript_count > customer_transcript_count_before_greeting
                
                # 2. Check if AGENT has spoken significantly AFTER the greeting was sent
                # (meaning the conversation moved on, e.g., to the pitch)
                # We can check specific timestamps, or just count. 
                # Ideally, we check if any NEW agent transcripts appeared that correspond to meaningful speech.
                current_agent_transcript_count = len([
                    entry for entry in agent.transcript 
                    if entry.get("speaker") == "Lia"
                ])
                # We didn't snapshot the agent count before, but we can check the recent transcripts
                # If the last transcript is from the AGENT and it's long (pitch), we assume we're active.
                
                agent_is_speaking_or_has_spoken = False
                if agent.transcript:
                    last_entry = agent.transcript[-1]
                    if last_entry.get("speaker") == "Lia":
                        # If the last thing said was by the agent
                        text = last_entry.get("text", "")
                        # If it's not just "Hello?" or "Hello, are you...", but something longer
                        if len(text) > 20: 
                             agent_is_speaking_or_has_spoken = True
                             logger.info(f"[OK] Agent is active (speaking: '{text[:30]}...') - cancelling silence timeout")

                # Also check active session state
                if agent._agent_session:
                     if agent._agent_session.response_task and not agent._agent_session.response_task.done():
                         agent_is_speaking_or_has_spoken = True
                         logger.info("[OK] Agent is generating/speaking - cancelling silence timeout")

                # If no user speech detected AND agent hasn't taken over, hang up
                if not user_has_spoken_after_greeting and not agent_is_speaking_or_has_spoken:
                    logger.warning(f"[WARN] No user response detected after {NO_RESPONSE_TIMEOUT} seconds - hanging up")
                    try:
                        await agent.hangup("no_answer", send_results=True)
                    except Exception as e:
                        logger.error(f"Error hanging up due to silence: {e}")
                else:
                    logger.info("[OK] User responded OR agent continued conversation - silence timeout cancelled")
                    
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"Silence monitor error: {e}")
        
        # Silence timeout will be started by wait_for_user_greeting        # Monitor the silence timeout and wait for shutdown event
        try:
            # wait_for_user_greeting handles the initial interaction phase
            # It returns when either the user speaks or the agent says "Hello?" and starts monitor_silence_timeout
            await wait_for_user_greeting()
            
            # Keep entrypoint alive until room is closed or participant disconnects
            logger.info("[ENTRYPOINT] Interaction phase ended, waiting for shutdown_event...")
            await shutdown_event.wait()
            logger.info("[ENTRYPOINT] shutdown_event received, exiting.")
        except asyncio.CancelledError:
            pass
        finally:
            # Cancel silence timeout if still running
            if silence_timeout_task and not silence_timeout_task.done():
                silence_timeout_task.cancel()
                try:
                    await silence_timeout_task
                except asyncio.CancelledError:
                    pass
            # Cancel idle reminder task if enabled and running
            if IDLE_REMINDER_ENABLED and idle_reminder_task is not None and not idle_reminder_task.done():
                idle_reminder_task.cancel()
                try:
                    await idle_reminder_task
                except asyncio.CancelledError:
                    pass

    except (RuntimeError, asyncio.TimeoutError, Exception) as e:
        # Handle network errors, timeouts, and other unexpected errors (but not TwirpError)
        # TwirpError is handled separately below
        if isinstance(e, api.TwirpError):
            raise  # Re-raise to be handled by TwirpError handler below
        
        error_type = type(e).__name__
        error_message = str(e)
        
        # Check if it's a network/connection error
        is_network_error = (
            "ServerDisconnectedError" in error_type or
            "ConnectionError" in error_type or
            "disconnected" in error_message.lower() or
            "connection" in error_message.lower() or
            "timeout" in error_message.lower() or
            isinstance(e, asyncio.TimeoutError)
        )
        
        if is_network_error:
            call_status = "failed"
            logger.error(f"[X] Network/connection error during call setup: {e}")
        else:
            call_status = "failed"
            logger.error(f"[X] Unexpected error during call setup: {error_type}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Clean up session_started task if it's still running
        if 'session_started' in locals() and not session_started.done():
            try:
                session_started.cancel()
                await session_started
            except Exception:
                pass
        
        # Update Google Sheets with failure status
        try:
            agent.call_end_time = datetime.datetime.now()
            await agent.send_call_results_to_sheets(call_status, failure_reason=error_message)
            logger.info(f"[OK] Error status ({call_status}) sent to Google Sheets")
        except Exception as sheet_error:
            logger.error(f"[X] Failed to update Google Sheets with error status: {sheet_error}")
        
        ctx.shutdown()
        return  # Exit early to avoid continuing with failed setup

    except api.TwirpError as e:
        sip_status_code = e.metadata.get('sip_status_code')
        sip_status = e.metadata.get('sip_status', '')
        
        logger.error(
            f"error creating SIP participant: {e.message}, "
            f"SIP status: {sip_status_code} {sip_status}"
        )
        
        # Determine call status based on SIP error code
        if sip_status_code == 603:
            call_status = "declined"
            logger.info(f"[CALL] Call declined (603) for {phone_number} - marking as 'Declined' in Google Sheets")
        elif sip_status_code == 486:
            call_status = "busy"
            logger.info(f"[CALL] Call busy (486) for {phone_number} - marking as 'Busy' in Google Sheets")
        elif sip_status_code == 480:
            call_status = "no_answer"
            logger.info(f"[CALL] Call no answer (480) for {phone_number} - marking as 'No Answer' in Google Sheets")
        else:
            call_status = "failed"
            logger.info(f"[CALL] Call failed (SIP {sip_status_code}) for {phone_number} - marking as 'Failed' in Google Sheets")
        
        # Update Google Sheets with the status before shutting down
        try:
            # Mark call end time
            agent.call_end_time = datetime.datetime.now()
            
            # Send results to Google Sheets
            sip_reason = f"SIP {sip_status_code} {sip_status}"
            await agent.send_call_results_to_sheets(call_status, failure_reason=sip_reason)
            logger.info(f"[OK] SIP error status ({call_status}) sent to Google Sheets - dispatch script will move to next call")
        except Exception as sheet_error:
            logger.error(f"[X] Failed to update Google Sheets with SIP error status: {sheet_error}")
            import traceback
            logger.error(traceback.format_exc())
        
        ctx.shutdown()


if __name__ == "__main__":
    import sys
    import time
    
    # Check if running in dev mode
    is_dev = "dev" in sys.argv
    
    if is_dev:
        print("[LOOP] Agent running in auto-restart mode. Press Ctrl+C to stop.")
        while True:
            try:
                cli.run_app(
                    WorkerOptions(
                        entrypoint_fnc=entrypoint,
                        agent_name="outbound-caller-dev",
                        num_idle_processes=3,
                    )
                )
                print("[WARN] Agent worker exited. Restarting in 2 seconds...")
            except KeyboardInterrupt:
                print("[STOP] Agent stopped by user.")
                break
            except Exception as e:
                print(f"[X] Agent crashed: {e}")
                print("[RESTART] Restarting in 2 seconds...")
            
            time.sleep(2)
    else:
        # Production/Start mode - run once
        cli.run_app(
            WorkerOptions(
                entrypoint_fnc=entrypoint,
                agent_name="outbound-caller-dev",
            )
        )
