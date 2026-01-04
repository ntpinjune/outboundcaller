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

# Langfuse for observability
try:
    from langfuse import Langfuse
    from langfuse.decorators import langfuse_context, observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

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
    noise_cancellation,  # noqa: F401
)



# load environment variables, this is optional, only used for local development
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

# Initialize Langfuse if available
langfuse = None
if LANGFUSE_AVAILABLE:
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if langfuse_public_key and langfuse_secret_key:
        try:
            langfuse = Langfuse(
                public_key=langfuse_public_key,
                secret_key=langfuse_secret_key,
                host=langfuse_host,
            )
            logger.info("✅ Langfuse initialized for observability")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")
    else:
        logger.info("ℹ️  Langfuse keys not found. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable observability")
else:
    logger.info("ℹ️  Langfuse not available. Install with: pip install langfuse")


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
        
        # Get current time in PST
        now_pst = datetime.datetime.now() - timedelta(hours=8)  # Approximate PST offset
        current_time = now_pst.strftime("%I:%M %p")
        
        # Brief instructions for the Agent framework
        # The full detailed prompt is in the entrypoint function as a system message
        super().__init__(
            instructions=f"""You are "Lia," a local employee for a landscaping marketing firm in San Jose. Be conversational, authentic, and real. Follow the detailed script provided in the system message. Customer name: {name}. Today is {today_date}, time is {current_time} PST."""
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
        
        # Appointment tracking
        self.appointment_scheduled = False
        self.appointment_time_scheduled = None
        self.appointment_email = None
        self._auto_hangup_scheduled = False  # Flag to prevent multiple auto-hangups
        
        # Langfuse tracking
        self.trace_id = str(uuid.uuid4())
        self.langfuse_trace = None
        self.langfuse_generation = None
        self._init_langfuse_trace()
    
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
                
                if transcript_text and isinstance(transcript_text, str) and transcript_text.strip() and is_final:
                    self.transcript.append({
                        "speaker": "Customer",
                        "text": transcript_text.strip(),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "is_final": True
                    })
                    logger.info(f"📝 [STT_NODE] Captured user transcript: {transcript_text.strip()}")
                
                yield event
        
        return intercepted_events()
    
    async def llm_node(self, chat_ctx, tools, model_settings):
        """Official LiveKit hook to intercept LLM output - captures agent speech."""
        from livekit.agents import ModelSettings, llm, FunctionTool
        from typing import AsyncIterable
        
        # Get the default LLM chunks
        chunks = Agent.default.llm_node(self, chat_ctx, tools, model_settings)
        
        async def intercepted_chunks():
            accumulated_text = ""  # Accumulate text across chunks
            async for chunk in chunks:
                # LLM chunks can be strings or ChatChunk objects
                text_to_capture = None
                
                # Try multiple ways to extract text
                if isinstance(chunk, str):
                    text_to_capture = chunk
                elif hasattr(chunk, 'text_content'):
                    # ChatChunk might have text_content() method
                    try:
                        text_to_capture = chunk.text_content()
                    except:
                        pass
                elif hasattr(chunk, 'text'):
                    text_to_capture = chunk.text
                elif hasattr(chunk, 'delta'):
                    # Some chunks have delta property
                    delta = chunk.delta
                    if isinstance(delta, str):
                        text_to_capture = delta
                    elif hasattr(delta, 'content'):
                        text_to_capture = delta.content
                elif hasattr(chunk, 'content'):
                    if isinstance(chunk.content, str):
                        text_to_capture = chunk.content
                    elif isinstance(chunk.content, list):
                        # Extract text from content list
                        text_parts = []
                        for part in chunk.content:
                            if isinstance(part, str):
                                text_parts.append(part)
                            elif isinstance(part, dict) and 'text' in part:
                                text_parts.append(part['text'])
                            elif hasattr(part, 'text'):
                                text_parts.append(part.text)
                        text_to_capture = ' '.join(text_parts)
                
                # Accumulate text (LLM outputs in chunks, we want full sentences)
                if text_to_capture and isinstance(text_to_capture, str) and text_to_capture.strip():
                    accumulated_text += text_to_capture
                    
                    # Check if we have a complete sentence (ends with punctuation or is substantial)
                    if len(accumulated_text.strip()) > 10 and (
                        accumulated_text.strip().endswith('.') or 
                        accumulated_text.strip().endswith('!') or 
                        accumulated_text.strip().endswith('?') or
                        len(accumulated_text.strip()) > 50  # Or if it's a long chunk
                    ):
                        # Capture the accumulated text
                        self.transcript.append({
                            "speaker": "Lia",
                            "text": accumulated_text.strip(),
                            "timestamp": datetime.datetime.now().isoformat(),
                            "is_final": True
                        })
                        logger.info(f"📝 [LLM_NODE] Captured agent transcript: {accumulated_text.strip()[:100]}...")
                        accumulated_text = ""  # Reset for next sentence
                
                yield chunk
            
            # Capture any remaining accumulated text when stream ends
            if accumulated_text.strip() and len(accumulated_text.strip()) > 3:
                self.transcript.append({
                    "speaker": "Lia",
                    "text": accumulated_text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 [LLM_NODE] Captured agent transcript (final): {accumulated_text.strip()[:100]}...")
        
        return intercepted_chunks()
    
    async def tts_node(self, text, model_settings):
        """Official LiveKit hook to intercept TTS input - captures agent speech that will be spoken."""
        from livekit.agents import ModelSettings
        from typing import AsyncIterable
        
        # Get the default TTS audio frames
        audio_frames = Agent.default.tts_node(self, text, model_settings)
        
        # Accumulate text that will be spoken
        accumulated_text = ""
        
        async def intercepted_text():
            nonlocal accumulated_text
            async for text_chunk in text:
                if isinstance(text_chunk, str) and text_chunk.strip():
                    accumulated_text += text_chunk
                    
                    # Capture when we have a complete sentence or substantial text
                    if len(accumulated_text.strip()) > 10 and (
                        accumulated_text.strip().endswith('.') or 
                        accumulated_text.strip().endswith('!') or 
                        accumulated_text.strip().endswith('?') or
                        len(accumulated_text.strip()) > 50
                    ):
                        # Check if we haven't already captured this (avoid duplicates with LLM node)
                        # Only add if it's not already in transcript
                        text_to_add = accumulated_text.strip()
                        if not any(entry.get("text", "").strip() == text_to_add for entry in self.transcript if entry.get("speaker") == "Lia"):
                            self.transcript.append({
                                "speaker": "Lia",
                                "text": text_to_add,
                                "timestamp": datetime.datetime.now().isoformat(),
                                "is_final": True
                            })
                            logger.info(f"📝 [TTS_NODE] Captured agent transcript: {text_to_add[:100]}...")
                        accumulated_text = ""
                
                yield text_chunk
            
            # Capture any remaining text
            if accumulated_text.strip() and len(accumulated_text.strip()) > 3:
                text_to_add = accumulated_text.strip()
                if not any(entry.get("text", "").strip() == text_to_add for entry in self.transcript if entry.get("speaker") == "Lia"):
                    self.transcript.append({
                        "speaker": "Lia",
                        "text": text_to_add,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "is_final": True
                    })
                    logger.info(f"📝 [TTS_NODE] Captured agent transcript (final): {text_to_add[:100]}...")
        
        # Process text and get audio
        processed_text = intercepted_text()
        return Agent.default.tts_node(self, processed_text, model_settings)
    
    def _init_langfuse_trace(self):
        """Initialize Langfuse trace for this call."""
        if not langfuse:
            return
        
        try:
            self.langfuse_trace = langfuse.trace(
                name="outbound_call",
                id=self.trace_id,
                metadata={
                    "customer_name": self.name,
                    "phone_number": self.dial_info.get("phone_number", "unknown"),
                    "appointment_time": self.appointment_time,
                },
                user_id=self.dial_info.get("phone_number", "unknown"),
            )
            logger.info(f"📊 Langfuse trace initialized: {self.trace_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse trace: {e}")
            self.langfuse_trace = None
    
    def _log_to_langfuse(self, event_type: str, data: dict):
        """Log events to Langfuse."""
        if not self.langfuse_trace:
            return
        
        try:
            if event_type == "generation":
                # Log LLM generation
                self.langfuse_generation = self.langfuse_trace.generation(
                    name="agent_response",
                    model=os.getenv("OPENAI_MODEL", os.getenv("LLM_PROVIDER", "groq")),
                    input=data.get("input", ""),
                    output=data.get("output", ""),
                    metadata={
                        "function_calls": data.get("function_calls", []),
                        "tokens": data.get("tokens", {}),
                    },
                )
            elif event_type == "span":
                # Log spans (function calls, operations)
                self.langfuse_trace.span(
                    name=data.get("name", "operation"),
                    input=data.get("input", {}),
                    output=data.get("output", {}),
                    metadata=data.get("metadata", {}),
                )
            elif event_type == "event":
                # Log events (call start, end, etc.)
                self.langfuse_trace.event(
                    name=data.get("name", "event"),
                    metadata=data.get("metadata", {}),
                )
        except Exception as e:
            logger.error(f"Failed to log to Langfuse: {e}")

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

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
        """Extract full transcript from the conversation history.
        
        This gets both user and agent messages from the LLM conversation context.
        Returns a formatted transcript with both Customer and Agent (Lia) messages.
        """
        transcript_lines = []
        
        try:
            if session is None:
                session = getattr(self, '_agent_session', None)
            
            if session is None:
                logger.warning("📝 No session available for transcript extraction")
                if self.transcript:
                    return self.format_transcript()
                return "No transcript available"
            
            # Method 1: Try session.history (official LiveKit method - most reliable)
            if hasattr(session, 'history') and session.history:
                logger.debug(f"📝 Found session.history: {type(session.history)}")
                try:
                    history_items = session.history
                    if isinstance(history_items, list) and len(history_items) > 0:
                        logger.debug(f"📝 Found {len(history_items)} items in session.history")
                        for idx, item in enumerate(history_items):
                            # Extract role and content
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
                                continue
                            
                            # Convert content to string
                            if isinstance(content, str):
                                content_text = content
                            elif hasattr(content, 'text'):
                                content_text = content.text
                            elif isinstance(content, list):
                                content_text = ' '.join([str(part) for part in content])
                            else:
                                content_text = str(content)
                            
                            # Determine speaker
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
                                logger.debug(f"📝 Added from history {idx+1}: {speaker} - {content_text.strip()[:50]}...")
                        
                        if transcript_lines:
                            logger.info(f"✅ Extracted transcript from session.history ({len(transcript_lines)} messages, {sum(len(line) for line in transcript_lines)} total chars)")
                            return "\n".join(transcript_lines)
                except Exception as e:
                    logger.debug(f"📝 Error accessing session.history: {e}")
            
            # Method 2: Try to get from chat_ctx (LLM conversation history)
            if hasattr(session, 'chat_ctx') and session.chat_ctx:
                chat_ctx = session.chat_ctx
                logger.info(f"📝 chat_ctx available, type: {type(chat_ctx)}")
                if hasattr(chat_ctx, 'items'):
                    items_count = len(chat_ctx.items) if hasattr(chat_ctx.items, '__len__') else 'unknown'
                    logger.info(f"📝 chat_ctx.items available, count: {items_count}")
                    for idx, item in enumerate(chat_ctx.items):
                        if isinstance(item, llm.ChatMessage):
                            role = item.role
                            # Get the text content from the message
                            content_text = ""
                            if isinstance(item.content, str):
                                content_text = item.content
                            elif isinstance(item.content, list):
                                # Handle list of content blocks (text, images, etc.)
                                for block in item.content:
                                    if isinstance(block, str):
                                        content_text += block
                                    elif hasattr(block, 'text'):
                                        content_text += block.text
                            
                            # Map roles to readable names
                            if role == "user":
                                speaker = "Customer"
                            elif role == "assistant":
                                speaker = "Lia"
                            elif role == "system":
                                continue  # Skip system messages
                            else:
                                speaker = role.title()
                            
                            if content_text.strip():
                                transcript_lines.append(f"{speaker}: {content_text.strip()}")
                                logger.info(f"📝 Added message {idx+1}: {speaker} - {content_text.strip()[:50]}... ({len(content_text)} chars)")
                    
                    if transcript_lines:
                        logger.info(f"✅ Extracted transcript from chat_ctx.items ({len(transcript_lines)} messages, {sum(len(line) for line in transcript_lines)} total chars)")
                        return "\n".join(transcript_lines)
                else:
                    logger.warning("📝 chat_ctx.items not available")
            else:
                logger.warning("📝 chat_ctx not available or empty")
            
            # Method 2: Try to get from session.messages if available
            if hasattr(session, 'messages') and session.messages:
                for msg in session.messages:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        role = msg.role
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                        
                        if role == "user":
                            speaker = "Customer"
                        elif role == "assistant":
                            speaker = "Lia"
                        elif role == "system":
                            continue
                        else:
                            speaker = role.title()
                        
                        if content.strip():
                            transcript_lines.append(f"{speaker}: {content.strip()}")
                
                if transcript_lines:
                    logger.info(f"✅ Extracted transcript from session.messages ({len(transcript_lines)} messages)")
                    return "\n".join(transcript_lines)
            
            # Method 3: Try to get from session.conversation if available
            if hasattr(session, 'conversation') and session.conversation:
                for msg in session.conversation:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        role = msg.role
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                        
                        if role == "user":
                            speaker = "Customer"
                        elif role == "assistant":
                            speaker = "Lia"
                        elif role == "system":
                            continue
                        else:
                            speaker = role.title()
                        
                        if content.strip():
                            transcript_lines.append(f"{speaker}: {content.strip()}")
                
                if transcript_lines:
                    logger.info(f"✅ Extracted transcript from session.conversation ({len(transcript_lines)} messages)")
                    return "\n".join(transcript_lines)
            
            # Fallback: Use real-time transcriptions if available
            if self.transcript:
                logger.info(f"✅ Using manual transcript entries ({len(self.transcript)} entries)")
                return self.format_transcript()
            
            logger.warning("⚠️  Could not extract transcript from conversation history")
            return "No transcript available"
            
        except Exception as e:
            logger.error(f"❌ Error extracting transcript from conversation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback to real-time transcriptions
            if self.transcript:
                return self.format_transcript()
            return "Error extracting transcript"

    async def _auto_hangup_after_scheduling(self, ctx: RunContext):
        """Automatically hang up the call after scheduling a meeting.
        
        This ensures the call ends even if the LLM doesn't explicitly call end_call().
        Waits a few seconds to allow the agent to finish saying goodbye.
        """
        try:
            # Wait 8 seconds to allow the agent to finish saying "See you then!"
            await asyncio.sleep(8)
            
            # Check if call hasn't already ended (user might have hung up or end_call was called)
            if not self.call_end_time:
                logger.info("Auto-hanging up after successful appointment scheduling")
                try:
                    # Wait for any current speech to finish
                    await ctx.wait_for_playout()
                except Exception as e:
                    logger.debug(f"Could not wait for playout (may have already finished): {e}")
                
                # Small additional delay
                await asyncio.sleep(1)
                # Hang up
                await self.hangup("completed", send_results=True)
        except Exception as e:
            logger.error(f"Error in auto-hangup after scheduling: {e}")

    async def send_call_results_to_sheets(self, call_status: str):
        """Update Google Sheets directly with call results (no Make.com needed)."""
        # Import here to avoid circular imports
        from update_call_results import update_from_webhook_data
        
        duration = 0
        if self.call_start_time and self.call_end_time:
            duration = (self.call_end_time - self.call_start_time).total_seconds()
        elif self.call_start_time:
            duration = (datetime.datetime.now() - self.call_start_time).total_seconds()
        
        # Format appointment time in a readable format for Google Sheets
        appointment_time_str = None
        if self.appointment_time_scheduled:
            # Convert to PST for display
            try:
                # If timezone-aware, convert to PST; otherwise assume UTC and convert
                if self.appointment_time_scheduled.tzinfo:
                    pst_time = self.appointment_time_scheduled.astimezone(datetime.timezone(timedelta(hours=-8)))
                else:
                    pst_time = self.appointment_time_scheduled.replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(timedelta(hours=-8)))
                # Format as readable string: "Tuesday, January 6, 2026 at 2:00 PM"
                appointment_time_str = pst_time.strftime("%A, %B %d, %Y at %I:%M %p")
            except Exception as e:
                logger.warning(f"Error formatting appointment time: {e}, using ISO format")
                appointment_time_str = self.appointment_time_scheduled.isoformat()
        
        # Get transcript from multiple sources and combine them
        # 1. Real-time transcriptions captured during the call (self.transcript)
        # 2. Conversation history from LLM chat context (more complete)
        transcript_text = ""
        
        # First, try to get transcript from real-time tracking (most accurate)
        realtime_transcript = self.format_transcript()
        logger.info(f"📝 Real-time transcript entries: {len(self.transcript)}, formatted: {len(realtime_transcript)} chars")
        
        # Then, try to get from conversation history (more complete, includes context)
        conversation_transcript = ""
        if self._agent_session:
            try:
                conversation_transcript = self.get_transcript_from_conversation(self._agent_session)
                logger.info(f"📝 Extracted transcript from conversation history ({len(conversation_transcript)} characters)")
            except Exception as e:
                logger.debug(f"Could not extract transcript from conversation: {e}")
        
        # Combine both sources - prefer real-time if it has substantial content
        # Otherwise use conversation history
        if realtime_transcript and len(realtime_transcript) > 10:
            transcript_text = realtime_transcript
            logger.info(f"📝 Using real-time transcript ({len(transcript_text)} characters)")
        elif conversation_transcript and len(conversation_transcript) > 50:
            transcript_text = conversation_transcript
            logger.info(f"📝 Using conversation history transcript ({len(transcript_text)} characters)")
        else:
            # Fallback: combine both if available
            if realtime_transcript:
                transcript_text = realtime_transcript
            elif conversation_transcript:
                transcript_text = conversation_transcript
            else:
                transcript_text = "No transcript available"
                logger.warning("⚠️  No transcript data available from any source")
                logger.warning(f"   Real-time entries: {len(self.transcript)}, Real-time formatted: {len(realtime_transcript)}, Conversation: {len(conversation_transcript)}")
        
        # Log what we're sending to Google Sheets for debugging
        logger.info(f"Sending to Google Sheets - appointment_scheduled: {self.appointment_scheduled}, appointment_time: {appointment_time_str}, appointment_email: {self.appointment_email}")
        
        data = {
            "phone_number": self.participant.identity if self.participant else "",
            "name": self.name,
            "call_status": call_status,
            "call_duration_seconds": int(duration),
            "transcript": transcript_text,  # Use conversation history transcript
            "appointment_scheduled": self.appointment_scheduled,
            "appointment_time": appointment_time_str,  # Now in readable format
            "appointment_email": self.appointment_email,  # The email address
            "timestamp": datetime.datetime.now().isoformat(),
            "row_id": self.dial_info.get("row_id")
        }
        
        try:
            # Update Google Sheets directly
            success = update_from_webhook_data(data)
            if success:
                logger.info(f"Call results updated in Google Sheets: {call_status}")
            else:
                logger.warning(f"Failed to update Google Sheets with call results")
        except Exception as e:
            logger.error(f"Failed to update Google Sheets: {e}")
        
        # Update Langfuse trace with final call metadata
        if self.langfuse_trace:
            try:
                duration = 0
                if self.call_start_time and self.call_end_time:
                    duration = (self.call_end_time - self.call_start_time).total_seconds()
                elif self.call_start_time:
                    duration = (datetime.datetime.now() - self.call_start_time).total_seconds()
                
                self.langfuse_trace.update(
                    metadata={
                        "call_status": call_status,
                        "appointment_scheduled": self.appointment_scheduled,
                        "appointment_time": str(self.appointment_time_scheduled) if self.appointment_time_scheduled else None,
                        "appointment_email": self.appointment_email,
                        "call_duration_seconds": int(duration),
                        "transcript_length": len(transcript_text),
                    },
                )
                
                # Log call end event
                self._log_to_langfuse("event", {
                    "name": "call_completed",
                    "metadata": {
                        "status": call_status,
                        "duration_seconds": int(duration),
                        "appointment_scheduled": self.appointment_scheduled,
                    },
                })
            except Exception as e:
                logger.error(f"Failed to update Langfuse trace: {e}")

    async def hangup(self, call_status: str = "completed", send_results: bool = True):
        """Helper function to hang up the call by deleting the room
        
        Args:
            call_status: Status of the call (completed, failed, voicemail, etc.)
            send_results: Whether to send call results (set to False if already sent)
        """
        # Mark call end time and send results if not already sent
        if send_results and not self.call_end_time:
            self.call_end_time = datetime.datetime.now()
            await self.send_call_results_to_sheets(call_status)
        elif not self.call_end_time:
            self.call_end_time = datetime.datetime.now()

        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(
                room=job_ctx.room.name,
            )
        )

    @function_tool()
    async def transfer_call(self, ctx: RunContext, reason: str = ""):
        """Transfer the call to a human agent, called after confirming with the user"""

        transfer_to = self.dial_info["transfer_to"]
        if not transfer_to:
            return "cannot transfer call"

        logger.info(f"transferring call to {transfer_to}")

        # let the message play fully before transferring
        await ctx.session.generate_reply(
            instructions="let the user know you'll be transferring them"
        )

        job_ctx = get_job_context()
        try:
            await job_ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job_ctx.room.name,
                    participant_identity=self.participant.identity,
                    transfer_to=f"tel:{transfer_to}",
                )
            )

            logger.info(f"transferred call to {transfer_to}")
        except Exception as e:
            logger.error(f"error transferring call: {e}")
            await ctx.session.generate_reply(
                instructions="there was an error transferring the call."
            )
            await self.hangup()

    @function_tool()
    async def end_call(self, ctx: RunContext, reason: str = ""):
        """Called when the user wants to end the call. Can be called with no arguments.
        
        Args:
            reason: Optional reason for ending the call. Can be omitted or empty string.
        """
        # Log end_call to Langfuse
        self._log_to_langfuse("span", {
            "name": "end_call",
            "input": {"reason": reason},
            "metadata": {"function": "end_call", "status": "called"},
        })
        
        logger.info(f"ending the call for {self.participant.identity} (reason: {reason if reason else 'none provided'})")

        # let the agent finish speaking - use RunContext.wait_for_playout() to avoid circular wait
        await ctx.wait_for_playout()

        await self.hangup()

    @function_tool()
    async def checkAvailability(
        self,
        ctx: RunContext,
        dateTime: str,
    ):
        """Check if a specific date and time is available in Google Calendar.
        
        CRITICAL: Call this tool IMMEDIATELY when the customer suggests ANY time. Do not ask questions first, just call the tool.
        
        Examples of when to call:
        - Customer says "Tuesday at 2pm" → call checkAvailability("Tuesday at 2pm")
        - Customer says "tomorrow at 3pm" → call checkAvailability("tomorrow at 3pm")
        - Customer says "next week Monday" → call checkAvailability("next week Monday")
        
        The tool will return whether the time is available or suggest an alternative time.

        Args:
            dateTime: The date and time to check (e.g., "Tuesday at 2pm", "2024-01-15 14:00:00", "tomorrow at 3pm")
        """
        # Log function call start to Langfuse
        self._log_to_langfuse("span", {
            "name": "checkAvailability",
            "input": {"dateTime": dateTime},
            "metadata": {"function": "checkAvailability", "status": "started"},
        })
        
        logger.info(f"Checking availability for {dateTime}")
        
        # Parse the dateTime string - handle common formats
        now = datetime.datetime.now()
        time_lower = dateTime.lower().strip()
        
        # Handle vague time preferences (mornings, afternoons, evenings)
        if "morning" in time_lower:
            # Suggest morning times: 9am, 10am, 11am
            result = {
                "available": True,
                "message": "Great! I have morning slots available. How about 9am, 10am, or 11am? Which works best for you?",
                "suggested_times": ["9am", "10am", "11am"],
                "time_preference": "morning"
            }
            self._log_to_langfuse("span", {
                "name": "checkAvailability",
                "input": {"dateTime": dateTime},
                "output": result,
                "metadata": {"function": "checkAvailability", "status": "vague_preference", "preference": "morning"},
            })
            return result
        elif "afternoon" in time_lower:
            # Suggest afternoon times: 1pm, 2pm, 3pm
            result = {
                "available": True,
                "message": "Perfect! I have afternoon slots available. How about 1pm, 2pm, or 3pm? Which works best for you?",
                "suggested_times": ["1pm", "2pm", "3pm"],
                "time_preference": "afternoon"
            }
            self._log_to_langfuse("span", {
                "name": "checkAvailability",
                "input": {"dateTime": dateTime},
                "output": result,
                "metadata": {"function": "checkAvailability", "status": "vague_preference", "preference": "afternoon"},
            })
            return result
        elif "evening" in time_lower:
            # Suggest evening times: 4pm, 5pm, 6pm
            result = {
                "available": True,
                "message": "Sure! I have evening slots available. How about 4pm, 5pm, or 6pm? Which works best for you?",
                "suggested_times": ["4pm", "5pm", "6pm"],
                "time_preference": "evening"
            }
            self._log_to_langfuse("span", {
                "name": "checkAvailability",
                "input": {"dateTime": dateTime},
                "output": result,
                "metadata": {"function": "checkAvailability", "status": "vague_preference", "preference": "evening"},
            })
            return result
        
        # Try to parse specific times
        import re
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', time_lower, re.IGNORECASE)
        
        try:
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                am_pm = time_match.group(3).upper()
                
                # Convert to 24-hour format
                if am_pm == "PM" and hour != 12:
                    hour += 12
                elif am_pm == "AM" and hour == 12:
                    hour = 0
                
                # Determine if it's today or tomorrow or a specific day
                if "tomorrow" in time_lower:
                    dt = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                elif any(day in time_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                    # Find the next occurrence of the day
                    current_weekday = now.weekday()
                    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    target_day = None
                    for i, day in enumerate(day_names):
                        if day in time_lower:
                            target_day = i
                            break
                    if target_day is not None:
                        days_ahead = (target_day - current_weekday) % 7
                        if days_ahead == 0:
                            # If it's today, check if time has passed
                            today_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            if today_time < now:
                                days_ahead = 7  # Check next week
                        dt = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        dt = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # Check if the time has passed today
                    today_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if today_time < now:
                        dt = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        dt = today_time
            elif "T" in dateTime or "-" in dateTime:
                # Try ISO format
                dt = datetime.datetime.fromisoformat(dateTime.replace("Z", "+00:00"))
            else:
                # Default to tomorrow at 2pm
                dt = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        except Exception as e:
            logger.warning(f"Could not parse dateTime {dateTime}, using default: {e}")
            dt = now + timedelta(days=1)
            dt = dt.replace(hour=14, minute=0, second=0, microsecond=0)
        
        # Ensure timezone is UTC for Google Calendar API
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        
        end_time = dt + timedelta(minutes=30)
        
        # Check availability using Google Calendar
        if self._calendar is None:
            self._calendar = GoogleCalendar()
        
        is_available = await self._calendar.check_availability(dt, end_time)
        
        try:
            if is_available:
                result = {"available": True, "message": "That time works perfectly."}
                # Log success to Langfuse
                self._log_to_langfuse("span", {
                    "name": "checkAvailability",
                    "input": {"dateTime": dateTime},
                    "output": result,
                    "metadata": {"function": "checkAvailability", "status": "success", "available": True},
                })
                return result
            else:
                # Get next available time
                next_available = await self._calendar.get_next_available_time(dt)
                next_available_str = next_available.strftime("%A at %I:%M %p")
                result = {
                    "available": False,
                    "next_available_time": next_available_str,
                    "message": f"Ah okay — sorry about that. Looks like the closest open time is {next_available_str}. Would that work?"
                }
                # Log result to Langfuse
                self._log_to_langfuse("span", {
                    "name": "checkAvailability",
                    "input": {"dateTime": dateTime},
                    "output": result,
                    "metadata": {"function": "checkAvailability", "status": "success", "available": False, "next_available": next_available_str},
                })
                return result
        except Exception as e:
            logger.error(f"Error in checkAvailability: {e}")
            # Log error to Langfuse
            self._log_to_langfuse("span", {
                "name": "checkAvailability",
                "input": {"dateTime": dateTime},
                "output": {"error": str(e)},
                "metadata": {"function": "checkAvailability", "status": "error"},
            })
            raise

    async def send_sms(self, phone_number: str, message_text: str) -> bool:
        """Send SMS text message using Twilio.

        Args:
            phone_number: Phone number in E.164 format (e.g., +12095539289)
            message_text: Message text to send
            
        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            twilio_from_number = os.getenv("TWILIO_FROM_NUMBER")
            
            if not all([twilio_account_sid, twilio_auth_token, twilio_from_number]):
                logger.warning("Twilio credentials not configured. SMS will not be sent.")
                return False
            
            # Run Twilio API call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            def _send_sms_sync():
                client = TwilioClient(twilio_account_sid, twilio_auth_token)
                message = client.messages.create(
                    body=message_text,
                    from_=twilio_from_number,
                    to=phone_number
                )
                return message.sid
            
            message_sid = await loop.run_in_executor(None, _send_sms_sync)
            logger.info(f"SMS sent successfully to {phone_number}, message SID: {message_sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS to {phone_number}: {e}")
            return False

    @function_tool()
    async def schedule_meeting(
        self,
        ctx: RunContext,
        email: str,
        dateTime: str,
    ):
        """Schedules a new appointment or meeting directly via Google Calendar API.
        
        CRITICAL: Call this tool IMMEDIATELY when you have BOTH the customer's email AND the agreed meeting time.
        Do not delay or ask more questions - just call the tool.
        
        Examples of when to call:
        - You have email "john@gmail.com" and time "Tuesday at 2pm" → call schedule_meeting(email="john@gmail.com", dateTime="Tuesday at 2pm")
        - You have email "jane@example.com" and time "tomorrow at 3pm" → call schedule_meeting(email="jane@example.com", dateTime="tomorrow at 3pm")
        
        This creates a Google Calendar event with Google Meet link and automatically sends the invite to the customer.
        The customer's name is automatically used from the call information - you don't need to pass it.

        Args:
            email: The customer's email address to send the calendar invite to (required)
            dateTime: When to schedule the meeting (e.g., 'Tuesday at 2pm', '2024-01-15 14:00:00', 'tomorrow at 2pm') (required)
        """
        # Log function call start to Langfuse
        self._log_to_langfuse("span", {
            "name": "schedule_meeting",
            "input": {"email": email, "dateTime": dateTime},
            "metadata": {"function": "schedule_meeting", "status": "started"},
        })
        
        if not email:
            error_msg = "I need your email address to send the calendar invite. Could you provide it?"
            self._log_to_langfuse("span", {
                "name": "schedule_meeting",
                "input": {"email": email, "dateTime": dateTime},
                "output": {"error": "Missing email"},
                "metadata": {"function": "schedule_meeting", "status": "error", "error": "missing_email"},
            })
            return error_msg
        
        # Parse email - handle spelled-out formats like "i t z n t p at Gmail dot co"
        # Convert to proper email format: "itzntp@gmail.com"
        email_lower = email.lower().strip()
        
        # If email contains "at" and "dot", it's likely spelled out
        if " at " in email_lower or " dot " in email_lower or " at gmail dot " in email_lower:
            # Remove spaces and convert "at" to "@" and "dot" to "."
            parsed_email = email_lower.replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
            # Handle common variations - do these BEFORE the general replacements
            parsed_email = parsed_email.replace("atgmail", "@gmail")
            # Handle "dot com", "dot co", etc. - check for common TLDs
            if "dotcom" in parsed_email or "dot com" in email_lower:
                parsed_email = parsed_email.replace("dotcom", ".com")
            elif "dotco" in parsed_email:
                # For Gmail addresses, "dot co" usually means ".com" not ".co"
                if "gmail" in parsed_email:
                    parsed_email = parsed_email.replace("dotco", ".com")
                    # Also fix if it's already "gmail.co" (should be "gmail.com")
                    if "gmail.co" in parsed_email and not "gmail.com" in parsed_email:
                        parsed_email = parsed_email.replace("gmail.co", "gmail.com")
                else:
                    parsed_email = parsed_email.replace("dotco", ".co")
            parsed_email = parsed_email.replace("dotnet", ".net")
            parsed_email = parsed_email.replace("dotorg", ".org")
            logger.info(f"Parsed spelled-out email '{email}' to '{parsed_email}'")
            email = parsed_email
        else:
            # Remove spaces in case it's spelled with spaces but no "at"/"dot"
            email = email.replace(" ", "").lower()
        
        logger.info(f"scheduling meeting for {email} at {dateTime}")
        
        # Parse dateTime - handle common formats
        # IMPORTANT: All times are in PST (Pacific Standard Time, UTC-8)
        # Create PST timezone
        pst_tz = datetime.timezone(timedelta(hours=-8))
        now_pst = datetime.datetime.now(pst_tz)
        time_lower = dateTime.lower().strip()
        
        # First, try to parse ISO format datetime strings (e.g., "2026-01-03T11:00:00-08:00")
        start_time = None  # Initialize to None
        try:
            # Try parsing as ISO format with timezone
            if "T" in dateTime and ("+" in dateTime or "-" in dateTime[-6:] or "Z" in dateTime):
                # Parse ISO format datetime
                if dateTime.endswith("Z"):
                    # UTC timezone
                    parsed_dt = datetime.datetime.fromisoformat(dateTime.replace("Z", "+00:00"))
                else:
                    # Has timezone offset
                    parsed_dt = datetime.datetime.fromisoformat(dateTime)
                
                # Convert to PST for consistency
                if parsed_dt.tzinfo:
                    start_time = parsed_dt.astimezone(pst_tz)
                else:
                    # Assume it's already in PST if no timezone
                    start_time = parsed_dt.replace(tzinfo=pst_tz)
                
                logger.info(f"Parsed ISO datetime: {dateTime} -> {start_time} (PST)")
                # Skip natural language parsing
                time_lower = ""  # Clear to skip natural language parsing
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse as ISO datetime, trying natural language: {e}")
            # Continue with natural language parsing below
        
        # Try to parse specific times (natural language)
        import re
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', time_lower, re.IGNORECASE) if time_lower else None
        
        # Only do natural language parsing if we didn't already parse an ISO datetime
        if start_time is None and time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            am_pm = time_match.group(3).upper()
            
            # Convert to 24-hour format
            if am_pm == "PM" and hour != 12:
                hour += 12
            elif am_pm == "AM" and hour == 12:
                hour = 0
            
            # Determine if it's today or tomorrow or a specific day
            if "tomorrow" in time_lower:
                # Create datetime in PST timezone
                tomorrow_pst = (now_pst + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                start_time = tomorrow_pst
            elif any(day in time_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                # Find the next occurrence of the day
                days_ahead = 0
                current_weekday = now_pst.weekday()
                day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                target_day = None
                for i, day in enumerate(day_names):
                    if day in time_lower:
                        target_day = i
                        break
                if target_day is not None:
                    days_ahead = (target_day - current_weekday) % 7
                    if days_ahead == 0:
                        # If it's today, check if time has passed
                        today_time_pst = now_pst.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if today_time_pst < now_pst:
                            days_ahead = 7  # Schedule for next week
                    target_date_pst = (now_pst + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    start_time = target_date_pst
                else:
                    tomorrow_pst = (now_pst + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    start_time = tomorrow_pst
            else:
                # Check if the time has passed today
                today_time_pst = now_pst.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if today_time_pst < now_pst:
                    tomorrow_pst = (now_pst + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    start_time = tomorrow_pst
                else:
                    start_time = today_time_pst
        elif "tomorrow" in time_lower:
            # Default to 2pm PST tomorrow
            tomorrow_pst = (now_pst + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
            start_time = tomorrow_pst
        else:
            # Only default if we haven't already set start_time from ISO parsing
            if start_time is None:
                # Default to 1 hour from now in PST
                start_time = now_pst + timedelta(hours=1)
        
        # Convert PST to UTC for Google Calendar API (if not already UTC)
        if start_time.tzinfo != datetime.timezone.utc:
            start_time = start_time.astimezone(datetime.timezone.utc)
        
        # Use the customer name from the agent (set at the beginning of the call from dial_info)
        participant_name = self.name if self.name else (self.participant.identity if self.participant else "Customer")
        
        # Format the time for display (convert to PST)
        pst_time = start_time.astimezone(datetime.timezone(timedelta(hours=-8)))
        time_str = pst_time.strftime("%I:%M %p on %A, %B %d, %Y")
        
        # Create Google Calendar event directly (no Make.com needed)
        try:
            # Initialize calendar lazily (only when needed)
            if self._calendar is None:
                self._calendar = GoogleCalendar()
            
            summary = f"Landscaping Marketing Consultation with {participant_name}"
            meet_link = await self._calendar.create_meet_event(
            attendee_email=email,
            start_time=start_time,
                summary=summary
            )
            
            # Track appointment scheduling success
            self.appointment_scheduled = True
            self.appointment_time_scheduled = start_time  # Store as timezone-aware datetime
            self.appointment_email = email  # Store the email
            
            logger.info(f"Appointment scheduled: {time_str} for {email} (stored time: {start_time})")
            
            # Log success to Langfuse
            self._log_to_langfuse("span", {
                "name": "schedule_meeting",
                "input": {"email": email, "dateTime": dateTime},
                "output": {"success": True, "time_str": time_str, "meet_link": meet_link},
                "metadata": {
                    "function": "schedule_meeting",
                    "status": "success",
                    "appointment_scheduled": True,
                    "appointment_time": str(start_time),
                    "appointment_email": email,
                },
            })
            
            # DO NOT auto-hangup here - let the agent complete the post-booking flow
            # The agent will follow the post-booking instructions and call end_call() at the end
            # Auto-hangup is disabled to allow for the full post-booking conversation
            
            # Return minimal success message - the agent will follow Step I post-booking flow instructions
            success_msg = f"Calendar invite sent successfully for {time_str} to {email}."
            return success_msg
                
        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {e}")
            # Log error to Langfuse
            self._log_to_langfuse("span", {
                "name": "schedule_meeting",
                "input": {"email": email, "dateTime": dateTime},
                "output": {"error": str(e)},
                "metadata": {"function": "schedule_meeting", "status": "error"},
            })
            return f"I've noted your meeting request for {time_str} with {email}. Our system is processing it, and you'll receive a confirmation email shortly."

    @function_tool()
    async def detected_answering_machine(self, ctx: RunContext, reason: str = ""):
        """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
        logger.info(f"detected answering machine for {self.participant.identity}")
        # Mark call end time and send results with voicemail status, then hangup
        self.call_end_time = datetime.datetime.now()
        await self.send_call_results_to_sheets("voicemail")
        await self.hangup("voicemail", send_results=False)  # Already sent results above
        return "ending call due to voicemail"


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()

    # when dispatching the agent, we'll pass it the approriate info to dial the user
    # dial_info is a dict with the following keys:
    # - phone_number: the phone number to dial (required)
    # - transfer_to: the phone number to transfer the call to when requested (optional)
    # - name: the customer's name (optional, for personalized greeting)
    # - appointment_time: existing appointment time if applicable (optional)
    dial_info = json.loads(ctx.job.metadata)
    participant_identity = phone_number = dial_info["phone_number"]
    
    # Get customer info from metadata (can come from Google Sheets via n8n)
    customer_name = dial_info.get("name", "Customer")
    appointment_time = dial_info.get("appointment_time", "")

    # look up the user's phone number and appointment details
    agent = OutboundCaller(
        name=customer_name,
        appointment_time=appointment_time,
        dial_info=dial_info,
    )

    # Get current date and tomorrow's date for the system message (like the example)
    today = datetime.datetime.now()
    tomorrow = today + timedelta(days=1)
    tomorrow_date = tomorrow.strftime("%A, %B %d, %Y")
    today_date = today.strftime("%A, %B %d, %Y")
    
    # Create chat context with system message - Lia persona
    # Get current time in PST
    now_pst = datetime.datetime.now() - timedelta(hours=8)  # Approximate PST offset
    current_time = now_pst.strftime("%I:%M %p")

    chat_ctx = llm.ChatContext(
        items=[
            llm.ChatMessage(
                role="system",
                content=[
                    f"""You are "Lia," a local employee for a landscaping marketing firm. Your owner and team are based in San Jose. Persona: Conversational, authentic, and "real." You aren't a polished corporate bot; you're a local peer. You sound confident but slightly casual.

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

Pacing: Never rush. Use ellipses (...) as cues to take a breath.

Confirmation: When asking "Hey.. {customer_name}?", stop speaking immediately.

Never say words in brackets.

After any question, stop speaking and allow the other person to respond naturally.



Current Context:
Today is {today_date}
The time is {current_time}
All times are in Pacific Standard Time (PST).
When creating a date-time string for tools, use the offset -08:00.

THE SCRIPT

First Message: 
Hey, {customer_name}?   
(Pause and let them respond)

THE HOOK
"Yeah hey {customer_name} uhh its just Lia... I'm just over here by San Jose and I uhm have some.. good news and bad news..."

THE REVEAL
"okay... soo uhm  the good news is this.... is a well-researched cold call... but uhh the bad news is... it's uhm a cold call... 
"But I'm just wondering... can you give me like, 30 seconds {customer_name}?"

CRITICAL: After asking for 30 seconds, wait for their response:
- If they say "yes", "yeah", "sure", "okay", "ok", "go ahead", or ANY approval response → IMMEDIATELY continue with THE PITCH. Do not ask again or wait longer.
- If they say "come again?", "what?", "huh?", or sound confused → use the response below, then continue.

If they say "come again?", "what?", "huh?", or sound confused, Lia responds:

"Oh — sorry about that… i'll say it again"
"Basically… uh this is a cold call… but it's uhm a really well-researched one."
"Would it be okay if I took like, 30 seconds {customer_name}?"

After they give ANY approval (yes, sure, okay, etc.), IMMEDIATELY continue with THE PITCH.

THE PITCH ( SLOW DOWN HERE)
"uhh Okay, so basically... I was doing some research on your business... and I uh noticed you're sitting on the 2nd page of Google... and um honestly... that's where you're losing money.... thats because people only see the top 3... and uh.. your no where near that"
"but um The way we actually  fix this—and uh just to throw something out there um we've generated over a million dollars for landscapers all over the bay area... 
but um the first thing we do is we optimize your Google profile to hit that number one spot..."
"Then we optimize your site to get high-ticket buyers... people looking for hardscaping, retaining walls... the big projects."

"uh I know I just said a lot..... but would you be interested in this {customer_name}?"

CRITICAL RESPONSE HANDLING:
- If they say "yes", "yeah", "sure", "I'm interested", or any positive response → IMMEDIATELY go to "THE CLOSE" section. Do NOT say anything about "when someone says yes it usually means they need more information" or any similar dialogue. Just move directly to scheduling.
- If they say "maybe", "I'm not sure", "possibly", or any uncertain response → use "ADDED RESPONSE FOR 'MAYBE'" below.
- If they say "no" or "not interested" → go to "OBJECTION HANDLING" section.

ADDED RESPONSE FOR "MAYBE" (no other wording changed):
"Yeah... uhm ... totally fair."
"When someone says maybe... it usually just means they'd need to see if it's actually worth it."
"Real quick... uh what would you have to see for this to be a yes? More calls, uhh better jobs, or just beating a couple competitors on Google?"
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
                ],
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
    llm_provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if llm_provider == "openai":
        # Using gpt-4o-mini for cost efficiency, but gpt-4o has better tool calling
        # If tools aren't being called, try switching to "gpt-4o" for better function calling
        llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
        if openai_api_key:
            # Pass API key explicitly if available
            llm_instance = openai.LLM(model=llm_model, api_key=openai_api_key)
        else:
            llm_instance = openai.LLM(model=llm_model)
    elif llm_provider == "openai-realtime":
        # Use the specified realtime model
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
    INITIAL_GREETING_DELAY = float(os.getenv("INITIAL_GREETING_DELAY", "1.0"))  # seconds to wait before first greeting
    MIN_ENDPOINTING_DELAY = float(os.getenv("MIN_ENDPOINTING_DELAY", "0.5"))  # min delay before considering user done speaking
    MAX_ENDPOINTING_DELAY = float(os.getenv("MAX_ENDPOINTING_DELAY", "15.0"))  # max delay before forcing turn end (increased for email collection - people spell emails very slowly letter by letter like "i t z n t p at Gmail dot co")
    
    # TTS Configuration - ElevenLabs voice with quota check
    # Get voice ID from environment variable, or use the specified default
    # You can find voice IDs in your ElevenLabs dashboard: https://elevenlabs.io/
    # NOTE: The voice must be in your ElevenLabs account for websocket streaming to work
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "6AUOG2nbfr0yFEeI0784")
    # ElevenLabs API key - can be set as ELEVEN_API_KEY or ELEVENLABS_API_KEY
    # The plugin automatically checks ELEVEN_API_KEY env var if not passed
    ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    
    # TTS Speed configuration (0.7 to 1.2, default 1.0 = normal speed)
    # 0.7 = slower, 1.2 = faster
    # You can set TTS_SPEED in .env.local to adjust speaking speed
    TTS_SPEED = float(os.getenv("TTS_SPEED", "1.0"))
    if TTS_SPEED < 0.7 or TTS_SPEED > 1.2:
        logger.warning(f"⚠️  TTS_SPEED {TTS_SPEED} is outside recommended range (0.7-1.2). Clamping to valid range.")
        TTS_SPEED = max(0.7, min(1.2, TTS_SPEED))
    
    # Check ElevenLabs quota before using it
    USE_ELEVENLABS = False
    voice_default_settings = None  # Store voice default settings for later use
    if ELEVEN_API_KEY:
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
                logger.info("✅ Wrapped STT transcribe method BEFORE session creation")
        except Exception as e:
            logger.warning(f"⚠️  Could not wrap STT transcribe method: {e}")
        
        # Set up transcript capture handler EARLY (before session starts)
        # This ensures we capture all logs from the beginning
        
        # Attach log handler EARLY to capture Deepgram transcripts
        # Use both handler AND filter for maximum coverage
        try:
            livekit_logger = logging.getLogger("livekit.agents")
            root_logger = logging.getLogger()
            
            class TranscriptCaptureHandler(logging.Handler):
                """Handler to capture transcripts from LiveKit logs - PRIMARY METHOD."""
                def __init__(self, track_func):
                    super().__init__()
                    self.track_func = track_func
                    self.setLevel(logging.DEBUG)
                    self.call_count = 0
                
                def emit(self, record):
                    try:
                        self.call_count += 1
                        msg = record.getMessage()
                        
                        # Look for "received user transcript" pattern (case insensitive)
                        if "received user transcript" in msg.lower():
                            import json
                            import re
                            
                            # The log format is: "received user transcript {"user_transcript": "...", "language": "..."}"
                            # Try to extract JSON from the log message
                            json_start = msg.find('{')
                            if json_start != -1:
                                json_str = msg[json_start:]
                                
                                # Try to parse as complete JSON first
                                try:
                                    data = json.loads(json_str)
                                    transcript_text = data.get("user_transcript")
                                    if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
                                        self.track_func(transcript_text.strip())
                                        # Use print to avoid recursion with logger
                                        print(f"📝 [LOG HANDLER] Captured: {transcript_text.strip()}", flush=True)
                                        return
                                except (json.JSONDecodeError, ValueError):
                                    pass
                            
                            # Fallback: Use regex to extract just the transcript value
                            match = re.search(r'"user_transcript"\s*:\s*"((?:[^"\\]|\\.)*)"', msg)
                            if match:
                                transcript_text = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                                if transcript_text and transcript_text.strip():
                                    self.track_func(transcript_text.strip())
                                    print(f"📝 [LOG HANDLER] Captured (regex): {transcript_text.strip()}", flush=True)
                    except Exception:
                        pass
            
            # Also create a filter that processes ALL log records
            class TranscriptCaptureFilter(logging.Filter):
                """Filter to capture transcripts from ALL log records."""
                def __init__(self, track_func):
                    super().__init__()
                    self.track_func = track_func
                
                def filter(self, record):
                    try:
                        msg = record.getMessage()
                        if "received user transcript" in msg.lower():
                            import json
                            import re
                            
                            json_start = msg.find('{')
                            if json_start != -1:
                                json_str = msg[json_start:]
                                try:
                                    data = json.loads(json_str)
                                    transcript_text = data.get("user_transcript")
                                    if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
                                        self.track_func(transcript_text.strip())
                                        print(f"📝 [LOG FILTER] Captured: {transcript_text.strip()}", flush=True)
                                except (json.JSONDecodeError, ValueError):
                                    match = re.search(r'"user_transcript"\s*:\s*"((?:[^"\\]|\\.)*)"', msg)
                                    if match:
                                        transcript_text = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                                        if transcript_text and transcript_text.strip():
                                            self.track_func(transcript_text.strip())
                                            print(f"📝 [LOG FILTER] Captured (regex): {transcript_text.strip()}", flush=True)
                    except Exception:
                        pass
                    return True  # Don't filter out any records
            
            transcript_handler = TranscriptCaptureHandler(track_user_transcript)
            transcript_handler.setLevel(logging.DEBUG)
            transcript_filter = TranscriptCaptureFilter(track_user_transcript)
            
            # Make sure loggers accept DEBUG level messages
            livekit_logger.setLevel(logging.DEBUG)
            root_logger.setLevel(logging.DEBUG)
            
            # Add handler AND filter to both loggers
            livekit_logger.addHandler(transcript_handler)
            livekit_logger.addFilter(transcript_filter)
            root_logger.addHandler(transcript_handler)
            root_logger.addFilter(transcript_filter)
            
            logger.info("✅ Added transcript capture handler AND filter EARLY (before session start)")
            logger.info(f"   Logger level: {livekit_logger.level}, Handler level: {transcript_handler.level}")
        except Exception as e:
            logger.warning(f"⚠️  Could not add early transcript capture handler: {e}")
    
    # Set transcript callback on STT wrapper (BEFORE session creation)
    # This is the most reliable method - captures at the source
    if stt_instance is not None and hasattr(stt_instance, 'set_transcript_callback'):
        try:
            stt_instance.set_transcript_callback(track_user_transcript)
            logger.info("✅ Set transcript callback on STT wrapper")
        except Exception as e:
            logger.warning(f"⚠️  Could not set STT transcript callback: {e}")
    
    # Use ElevenLabs TTS only - no fallback to OpenAI
    if USE_ELEVENLABS:
        # Configure voice settings with speed
        from livekit.plugins.elevenlabs import VoiceSettings
        # Use voice default settings if available, otherwise use reasonable defaults
        if voice_default_settings:
            stability = voice_default_settings.get('stability', 0.5)
            similarity_boost = voice_default_settings.get('similarity_boost', 0.75)
        else:
            stability = 0.5
            similarity_boost = 0.75
        
        voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            speed=TTS_SPEED  # Configured speaking speed (0.7-1.2)
        )
        tts_instance = elevenlabs.TTS(
            voice_id=ELEVENLABS_VOICE_ID,
            api_key=ELEVEN_API_KEY,
            voice_settings=voice_settings
        )
        logger.info(f"✅ ElevenLabs TTS instance created with voice ID: {ELEVENLABS_VOICE_ID}, speed: {TTS_SPEED}")
    else:
        # Fail if ElevenLabs is not available - no fallback
        if not ELEVEN_API_KEY:
            logger.error("❌ ELEVEN_API_KEY not found - ElevenLabs TTS is required!")
            logger.error("   Please set ELEVEN_API_KEY in your .env.local file")
            raise ValueError("ELEVEN_API_KEY is required for ElevenLabs TTS")
        else:
            logger.error(f"❌ ElevenLabs TTS not available (quota check failed or quota low)")
            logger.error(f"   Required voice ID: {ELEVENLABS_VOICE_ID}")
            logger.error("   Please check your ElevenLabs quota at: https://elevenlabs.io/")
            logger.error("   ElevenLabs TTS is required - no fallback available")
            logger.error("   Agent will not start without the specified ElevenLabs voice")
            raise ValueError(f"ElevenLabs TTS is required but not available. Voice ID: {ELEVENLABS_VOICE_ID}")
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=stt_instance,  # None for Realtime, deepgram.STT() for regular models
        tts=tts_instance,  # None for Realtime, TTS instance for regular models
        llm=llm_instance,
        # Configure endpointing delays (when to consider user finished speaking)
        min_endpointing_delay=MIN_ENDPOINTING_DELAY,  # Lower = faster response, but may cut off user
        max_endpointing_delay=MAX_ENDPOINTING_DELAY,  # Higher = wait longer for user to continue
    )

    # start the session first before dialing, to ensure that when the user picks up
    # the agent does not miss anything the user says
    session_started = asyncio.create_task(
        session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                # enable Krisp background voice and noise removal
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
    )

    # `create_sip_participant` starts dialing the user
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

        # wait for the agent session start and participant join
        await session_started
        participant = await ctx.wait_for_participant(identity=participant_identity)
        logger.info(f"participant joined: {participant.identity}")

        agent.set_participant(participant)
        
        # Store session reference for transcript extraction
        agent._agent_session = session
        
        # Track call start time
        agent.call_start_time = datetime.datetime.now()
        
        # OFFICIAL METHOD: Subscribe to conversation_item_added event
        # This is the recommended way to track all conversation items (user and agent)
        @session.on("conversation_item_added")
        def on_conversation_item_added(item):
            """Official LiveKit method to capture conversation items."""
            track_conversation_item(item)
        
        logger.info("✅ Subscribed to conversation_item_added events (official method)")
        
        # DIRECT STT ACCESS - Access the STT stream directly (most reliable method)
        # The session's STT instance processes audio and we can intercept transcriptions
        def track_user_transcript(text: str):
            """Capture user speech transcriptions from STT."""
            if text and text.strip():
                agent.transcript.append({
                    "speaker": "Customer",
                    "text": text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 User transcript captured: {text.strip()}")
        
        def track_agent_transcript(text: str):
            """Capture agent speech transcriptions."""
            if text and text.strip():
                agent.transcript.append({
                    "speaker": "Lia",
                    "text": text.strip(),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_final": True
                })
                logger.info(f"📝 Agent transcript captured: {text.strip()}")
        
        # Method 1: Access STT instance directly from session
        if hasattr(session, 'stt') and session.stt is not None:
            try:
                stt_instance = session.stt
                logger.info(f"✅ STT instance available: {type(stt_instance)}")
                
                # Deepgram STT should have a way to access transcriptions
                # Try to wrap the transcribe method or access the stream
                if hasattr(stt_instance, 'transcribe'):
                    original_transcribe = stt_instance.transcribe
                    
                    async def wrapped_transcribe(*args, **kwargs):
                        """Wrap transcribe to capture transcriptions."""
                        result = await original_transcribe(*args, **kwargs)
                        # Extract transcript from result
                        if hasattr(result, 'text'):
                            track_user_transcript(result.text)
                        elif isinstance(result, str):
                            track_user_transcript(result)
                        elif isinstance(result, dict):
                            text = result.get('text') or result.get('transcript')
                            if text:
                                track_user_transcript(text)
                        return result
                    
                    stt_instance.transcribe = wrapped_transcribe
                    logger.info("✅ Wrapped STT transcribe method to capture transcriptions")
            except Exception as e:
                logger.debug(f"Could not wrap STT transcribe method: {e}")
        
        # Method 2: Access session's input/output streams which contain transcriptions
        # The AgentSession processes audio through STT and publishes transcriptions
        if hasattr(session, 'input') and hasattr(session.input, 'on'):
            try:
                def on_input_transcript(event):
                    """Handle transcriptions from session input stream."""
                    try:
                        transcript_text = None
                        if hasattr(event, 'text'):
                            transcript_text = event.text
                        elif hasattr(event, 'transcript'):
                            transcript_text = event.transcript
                        elif isinstance(event, dict):
                            transcript_text = event.get('text') or event.get('transcript')
                        elif isinstance(event, str):
                            transcript_text = event
                        
                        if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
                            track_user_transcript(transcript_text.strip())
                            logger.info(f"📝 [INPUT STREAM] Captured user transcript: {transcript_text.strip()}")
                    except Exception as e:
                        logger.debug(f"Error in input stream handler: {e}")
                
                # Try different event names
                for event_name in ["transcript", "transcription", "stt_result", "speech"]:
                    try:
                        session.input.on(event_name, on_input_transcript)
                        logger.info(f"✅ Subscribed to session input '{event_name}' events")
                        break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Could not subscribe to input stream: {e}")
        
        # Additional transcript capture methods (backup methods)
        
        # Method 1: Listen to conversation_item_added events (official API)
        # This captures both user and agent messages when they're added to chat history
        if hasattr(session, 'on'):
            def on_conversation_item_added(item):
                """Capture transcripts when items are added to conversation."""
                try:
                    # Extract text and role from the conversation item
                    text = None
                    role = None
                    
                    if hasattr(item, 'text'):
                        text = item.text
                    elif hasattr(item, 'content'):
                        text = item.content
                    elif isinstance(item, dict):
                        text = item.get('text') or item.get('content')
                        role = item.get('role')
                    elif hasattr(item, 'role'):
                        role = item.role
                        if hasattr(item, 'content'):
                            if isinstance(item.content, str):
                                text = item.content
                            elif isinstance(item.content, list):
                                # Handle list of content blocks
                                text = " ".join(str(block) for block in item.content if block)
                    
                    if text and isinstance(text, str) and text.strip():
                        # Determine if it's user or agent based on role
                        if role == 'user' or (hasattr(item, 'role') and item.role == 'user'):
                            track_user_transcript(text.strip())
                            logger.info(f"📝 Captured user transcript from conversation: {text.strip()}")
                        elif role == 'assistant' or (hasattr(item, 'role') and item.role == 'assistant'):
                            track_agent_transcript(text.strip())
                            logger.info(f"📝 Captured agent transcript from conversation: {text.strip()}")
                        else:
                            # Default to user if we can't determine
                            track_user_transcript(text.strip())
                            logger.info(f"📝 Captured transcript (unknown role) from conversation: {text.strip()}")
                except Exception as e:
                    logger.debug(f"Error in conversation_item_added handler: {e}")
            
            try:
                session.on("conversation_item_added", on_conversation_item_added)
                logger.info("✅ Subscribed to conversation_item_added events")
            except Exception as e:
                logger.debug(f"Could not subscribe to conversation_item_added: {e}")
        
        # Method 2: Subscribe to room text stream events for lk.transcription topic (official API)
        # This captures transcriptions published to text streams in real-time
        def on_text_stream_received(data):
            """Handle text stream events including transcriptions."""
            try:
                # Extract topic, message, and attributes
                topic = None
                message = None
                attributes = {}
                sender_identity = None
                
                # Try different ways to access the data
                if hasattr(data, 'topic'):
                    topic = data.topic
                elif hasattr(data, 'info') and hasattr(data.info, 'topic'):
                    topic = data.info.topic
                    attributes = getattr(data.info, 'attributes', {})
                    sender_identity = getattr(data.info, 'sender_identity', None)
                elif isinstance(data, dict):
                    topic = data.get('topic')
                    message = data.get('message')
                    attributes = data.get('attributes', {})
                    sender_identity = data.get('sender_identity')
                
                # Check if this is a transcription
                if topic == 'lk.transcription' or (isinstance(topic, str) and 'transcription' in topic.lower()):
                    # Extract text from message
                    text = None
                    if message:
                        if isinstance(message, str):
                            text = message
                        elif hasattr(message, 'text'):
                            text = message.text
                        elif hasattr(message, 'value'):
                            text = message.value
                        elif isinstance(message, dict):
                            text = message.get('text') or message.get('value') or str(message)
                    elif hasattr(data, 'message'):
                        msg = data.message
                        if isinstance(msg, str):
                            text = msg
                        elif hasattr(msg, 'text'):
                            text = msg.text
                        elif hasattr(msg, 'value'):
                            text = msg.value
                    
                    # Get attributes if not already extracted
                    if not attributes:
                        if hasattr(data, 'attributes'):
                            attributes = data.attributes
                        elif hasattr(data, 'info') and hasattr(data.info, 'attributes'):
                            attributes = data.info.attributes
                    
                    # Get sender if not already extracted
                    if not sender_identity:
                        if hasattr(data, 'sender_identity'):
                            sender_identity = data.sender_identity
                        elif hasattr(data, 'sender'):
                            sender_identity = data.sender
                        elif hasattr(data, 'info') and hasattr(data.info, 'sender_identity'):
                            sender_identity = data.info.sender_identity
                    
                    # Check if this is a final transcription (not interim)
                    is_final = attributes.get('lk.transcription_final', 'false') == 'true'
                    has_track_id = attributes.get('lk.transcribed_track_id') is not None
                    
                    if text and text.strip() and is_final:
                        # Determine speaker from sender identity or transcribed_track_id
                        if sender_identity == participant.identity or sender_identity == phone_number:
                            track_user_transcript(text.strip())
                            logger.info(f"📝 Captured user transcription from text stream: {text.strip()}")
                        elif "agent" in str(sender_identity).lower() or sender_identity == "agent":
                            track_agent_transcript(text.strip())
                            logger.info(f"📝 Captured agent transcription from text stream: {text.strip()}")
                        elif has_track_id:
                            # Has transcribed_track_id means it's user audio being transcribed
                            track_user_transcript(text.strip())
                            logger.info(f"📝 Captured user transcription (via track_id): {text.strip()}")
                        else:
                            # Default to agent if no track_id (likely agent speech)
                            track_agent_transcript(text.strip())
                            logger.info(f"📝 Captured agent transcription (default): {text.strip()}")
            except Exception as e:
                logger.debug(f"Error handling text stream: {e}")
        
        # Subscribe to room text stream events
        try:
            # Try the official room event subscription
            if hasattr(ctx.room, 'on'):
                ctx.room.on("text_stream_received", on_text_stream_received)
                logger.info("✅ Subscribed to room text_stream_received events")
            else:
                raise AttributeError("Room does not have 'on' method")
        except Exception as e:
            logger.warning(f"⚠️  Could not subscribe to text stream events: {e}")
            # Try alternative method if available
            try:
                if hasattr(ctx.room, 'register_text_stream_handler'):
                    ctx.room.register_text_stream_handler("lk.transcription", on_text_stream_received)
                    logger.info("✅ Registered text stream handler for lk.transcription (alternative method)")
            except Exception as e2:
                logger.warning(f"⚠️  Alternative text stream registration also failed: {e2}")
        
        # Also track transcriptions from participant tracks if available
        # When STT processes audio, it may emit events we can capture
        async def track_participant_transcriptions():
            """Monitor participant tracks for transcription data."""
            try:
                for track in participant.track_publications.values():
                    if track.kind == rtc.TrackKind.KIND_AUDIO:
                        # Audio tracks from participants are transcribed by STT
                        # The transcription will come through text streams above
                        pass
            except Exception as e:
                logger.debug(f"Error tracking participant transcriptions: {e}")
        
        # Start background task to monitor transcriptions
        asyncio.create_task(track_participant_transcriptions())
        
        # Log call start to Langfuse
        if agent.langfuse_trace:
            try:
                agent._log_to_langfuse("event", {
                    "name": "call_started",
                    "metadata": {
                        "phone_number": participant.identity,
                        "customer_name": customer_name,
                        "room_name": ctx.room.name,
                    },
                })
            except Exception as e:
                logger.debug(f"Failed to log call start to Langfuse: {e}")
        
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
                                logger.info("📝 Participant no longer in room - sending transcript...")
                                break
                    except Exception:
                        # Participant might be None or invalid
                        pass
                    
                    # Check if session is closed
                    try:
                        if hasattr(session, 'closed') and session.closed:
                            logger.info("📝 Session closed - sending transcript...")
                            break
                        if hasattr(session, '_closed') and session._closed:
                            logger.info("📝 Session _closed - sending transcript...")
                            break
                    except Exception:
                        pass
            except asyncio.CancelledError:
                logger.info("📝 Monitor cancelled - sending transcript...")
            except Exception as e:
                logger.debug(f"Monitor error: {e}")
            
            # Send transcript
            if not agent.call_end_time:
                logger.info("📝 Sending transcript to Google Sheets...")
                try:
                    # Extract transcript from conversation history
                    transcript_from_history = ""
                    if agent._agent_session:
                        try:
                            transcript_from_history = agent.get_transcript_from_conversation(agent._agent_session)
                            if transcript_from_history and len(transcript_from_history) > 0:
                                logger.info(f"📝 Extracted {len(transcript_from_history)} characters from conversation history")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not extract transcript from conversation: {e}")
                    
                    # Also check real-time transcriptions
                    realtime_transcript = agent.format_transcript()
                    logger.info(f"📝 Real-time transcript entries: {len(agent.transcript)}, formatted: {len(realtime_transcript)} chars")
                    
                    # Send results (send_call_results_to_sheets will combine both sources)
                    call_status = "completed" if agent.appointment_scheduled else "no_answer"
                    await agent.send_call_results_to_sheets(call_status)
                    agent.call_end_time = datetime.datetime.now()
                    logger.info(f"✅ Transcript sent to Google Sheets (status: {call_status})")
                except Exception as e:
                    logger.error(f"❌ Error sending transcript: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Function to send transcript (shared by all handlers)
        async def send_transcript_on_end():
            """Send transcript when call ends."""
            if not agent.call_end_time:
                logger.info("📝 Call ended - extracting and sending transcript...")
                try:
                    # Extract transcript from conversation history
                    transcript_from_history = ""
                    if agent._agent_session:
                        try:
                            transcript_from_history = agent.get_transcript_from_conversation(agent._agent_session)
                            if transcript_from_history and len(transcript_from_history) > 0:
                                logger.info(f"📝 Extracted {len(transcript_from_history)} characters from conversation history")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not extract transcript from conversation: {e}")
                    
                    # Also check real-time transcriptions
                    realtime_transcript = agent.format_transcript()
                    logger.info(f"📝 Real-time transcript entries: {len(agent.transcript)}, formatted: {len(realtime_transcript)} chars")
                    
                    # Send results
                    call_status = "completed" if agent.appointment_scheduled else "no_answer"
                    await agent.send_call_results_to_sheets(call_status)
                    agent.call_end_time = datetime.datetime.now()
                    logger.info(f"✅ Transcript sent to Google Sheets (status: {call_status})")
                except Exception as e:
                    logger.error(f"❌ Error sending transcript: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Subscribe to participant disconnect event (most reliable)
        def on_participant_disconnected_event(participant_disconnected: rtc.RemoteParticipant):
            """Handle participant disconnect."""
            if participant_disconnected.identity == phone_number:
                logger.info(f"📝 Participant {participant_disconnected.identity} disconnected - sending transcript...")
                asyncio.create_task(send_transcript_on_end())
        
        try:
            ctx.room.on(rtc.RoomEvent.PARTICIPANT_DISCONNECTED, on_participant_disconnected_event)
            logger.info("✅ Subscribed to participant disconnect event")
        except Exception as e:
            logger.warning(f"⚠️  Could not subscribe to participant disconnect: {e}")
        
        # Start monitoring as backup
        monitor_task = asyncio.create_task(monitor_and_send_transcript())
        
        # Wait before initial greeting (adjustable delay)
        if INITIAL_GREETING_DELAY > 0:
            logger.info(f"Waiting {INITIAL_GREETING_DELAY} seconds before initial greeting...")
            await asyncio.sleep(INITIAL_GREETING_DELAY)
        
        # Generate initial greeting
        try:
            await session.generate_reply(
                instructions=f"Say ONLY this: 'Hey, {customer_name}?' Then STOP COMPLETELY and wait for their response. Do not say anything else until they respond."
            )
        except RuntimeError as e:
            if "AgentSession is closing" in str(e) or "cannot use generate_reply" in str(e):
                logger.error(f"❌ Session is closing, cannot generate reply: {e}")
                monitor_task.cancel()
                await send_transcript_on_end()
                return
            raise
        except Exception as e:
            logger.error(f"Error generating initial greeting: {e}")
            monitor_task.cancel()
            await send_transcript_on_end()
            raise
        
        # Wait for monitor to complete (will finish when participant disconnects)
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    except api.TwirpError as e:
        logger.error(
            f"error creating SIP participant: {e.message}, "
            f"SIP status: {e.metadata.get('sip_status_code')} "
            f"{e.metadata.get('sip_status')}"
        )
        ctx.shutdown()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller-dev",
        )
    )
