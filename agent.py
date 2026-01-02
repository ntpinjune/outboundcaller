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
        self.session: Optional[AgentSession] = None  # Store session reference for transcript extraction
        
        # Appointment tracking
        self.appointment_scheduled = False
        self.appointment_time_scheduled = None
        self.appointment_email = None
        self._auto_hangup_scheduled = False  # Flag to prevent multiple auto-hangups

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
    
    def get_transcript_from_conversation(self, session: AgentSession) -> str:
        """Extract full transcript from the conversation history.
        
        This gets both user and agent messages from the LLM conversation context.
        """
        try:
            # Get the conversation history from the session's chat context
            chat_ctx = session.chat_ctx
            if not chat_ctx:
                return ""
            
            transcript_lines = []
            for item in chat_ctx.items:
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
            
            return "\n".join(transcript_lines)
        except Exception as e:
            logger.error(f"Error extracting transcript from conversation: {e}")
            return self.format_transcript()  # Fallback to old method

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
        
        # Get transcript from conversation history (preferred method)
        transcript_text = ""
        if self.session:
            try:
                transcript_text = self.get_transcript_from_conversation(self.session)
                logger.info(f"Extracted transcript from conversation history ({len(transcript_text)} characters)")
            except Exception as e:
                logger.warning(f"Could not extract transcript from conversation: {e}, using fallback")
                transcript_text = self.format_transcript()
        else:
            # Fallback to old method if session not available
            transcript_text = self.format_transcript()
        
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
        """Called when the user wants to end the call
        
        Args:
            reason: Optional reason for ending the call (can be empty string)
        """
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
        logger.info(f"Checking availability for {dateTime}")
        
        # Parse the dateTime string - handle common formats
        now = datetime.datetime.now()
        time_lower = dateTime.lower().strip()
        
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
        
        if is_available:
            return {"available": True, "message": "That time works perfectly."}
        else:
            # Get next available time
            next_available = await self._calendar.get_next_available_time(dt)
            next_available_str = next_available.strftime("%A at %I:%M %p")
        return {
                "available": False,
                "next_available_time": next_available_str,
                "message": f"Ah okay — sorry about that. Looks like the closest open time is {next_available_str}. Would that work?"
            }

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
        if not email:
            return "I need your email address to send the calendar invite. Could you provide it?"
        
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
            
            # Schedule automatic hangup after a short delay to allow the agent to say goodbye
            # This ensures the call ends even if the LLM doesn't call end_call()
            if not self._auto_hangup_scheduled:
                self._auto_hangup_scheduled = True
                asyncio.create_task(self._auto_hangup_after_scheduling(ctx))
            
            if meet_link:
                return f"Perfect! I've scheduled your meeting for {time_str} and sent a calendar invite to {email}. You'll receive the confirmation email shortly. See you then!"
            else:
                return f"Perfect! I've scheduled your meeting for {time_str} and sent a calendar invite to {email}. You'll receive the confirmation email shortly. See you then!"
                
        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {e}")
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
   - WHEN TO CALL: Immediately when customer suggests ANY time (e.g., "Tuesday at 2pm", "tomorrow at 3pm", "next week")
   - EXAMPLE: Customer says "How about Tuesday at 2pm?" → IMMEDIATELY call checkAvailability("Tuesday at 2pm")
   - DO NOT say "let me check" - just call the tool silently
   - The tool will return if the time is available or suggest another time

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

Step D: Combine and Check Calendar Availability
**CRITICAL: IMMEDIATELY after they provide the day, combine their answers (day + time) and call the checkAvailability tool.**
Example: If they said "mornings", "10am", and "Tuesday", call checkAvailability("Tuesday at 10am") RIGHT NOW. Do not say "let me check" - just call the tool silently.

After the tool returns:
- If tool says available: "That time works perfectly."
- If tool says busy and gives next_available_time: "Ah okay — sorry about that. Looks like the closest open time is [next_available_time]. Would that work?"

Step E: Confirm the Time Works
Make sure the time works for both of you.
"That time works perfectly. Does that work for you?"
OR if they suggested an alternative: "Would that work?"

Wait for their confirmation (they'll say "yes", "sure", "that works", etc.).

Step F: Email Collection
"Okay, to lock that in... what's the best email to send the calendar invite to?"

Wait for them to provide their email. They might spell it out letter by letter like "i t z n t p at Gmail dot co".

Step G: Verify Email Letter by Letter
After they provide the email, you MUST verify it by spelling out ONLY the username part (before @) and domain name (like gmail) letter by letter.

CRITICAL RULES FOR EMAIL VERIFICATION:
- Spell out the username part (before @) letter by letter: "j... o... h... n"
- Say "at" as a word (not spelled out)
- Spell out the domain name (like gmail) letter by letter: "g... m... a... i... l"
- Say "dot" as a word (not spelled out)
- Say the extension (like com) as a word: "com" (not spelled out)

Examples:
- If they said "john@gmail.com", you say: "Just to make sure I got that right... that was j... o... h... n... at... g... m... a... i... l... dot... com. Is that correct?"
- If they said "i t z n t p at Gmail dot co", you say: "Just to make sure I got that right... that was i... t... z... n... t... p... at... g... m... a... i... l... dot... co. Is that correct?"

MANDATORY: Spell out ONLY the username and domain name letter by letter. Say "at", "dot", and the extension (com, co, etc.) as words.

Wait for their confirmation (they'll say "yes", "correct", "that's right", etc.).

Step H: The Booking
**STOP TALKING IMMEDIATELY** and call schedule_meeting(email="[the email you collected]", dateTime="[the agreed time]").
Example: If email is "john@gmail.com" and time is "Tuesday at 10am" (from combining "mornings", "10am", "Tuesday"), call schedule_meeting(email="john@gmail.com", dateTime="Tuesday at 10am") RIGHT NOW.

Do not say "let me schedule that" or "I'll create the event" - just call the tool immediately.

After the tool completes, say: "Perfect! I've sent the calendar invite to your email. See you then, {customer_name}!"

**CRITICAL: IMMEDIATELY after saying "See you then", you MUST call the end_call() tool to hang up the phone. Do not wait for a response - just call end_call() right away.**

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
        llm_instance = openai.LLM(model=llm_model)
    elif llm_provider == "openai-realtime":
        # Use the specified realtime model
        realtime_model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI Realtime model")
        llm_instance = openai.realtime.RealtimeModel(
            model=realtime_model,
            api_key=openai_api_key
        )  # Speech-to-speech, no TTS needed
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
    
    # Check ElevenLabs quota before using it
    USE_ELEVENLABS = False
    if ELEVEN_API_KEY:
        try:
            import requests
            headers = {"xi-api-key": ELEVEN_API_KEY}
            response = requests.get("https://api.elevenlabs.io/v1/user", headers=headers, timeout=5)
            if response.status_code == 200:
                user_data = response.json()
                char_count = user_data.get('subscription', {}).get('character_count', 0)
                char_limit = user_data.get('subscription', {}).get('character_limit', 0)
                remaining = char_limit - char_count
                
                if remaining > 100:  # Only use if more than 100 characters remaining
                    USE_ELEVENLABS = True
                    logger.info(f"Using ElevenLabs TTS with voice ID: {ELEVENLABS_VOICE_ID} ({remaining} chars remaining)")
                else:
                    logger.warning(f"ElevenLabs quota low ({remaining} chars remaining). Using OpenAI TTS instead.")
                    logger.warning("To use ElevenLabs: Upgrade your plan or wait for quota reset at https://elevenlabs.io/")
            else:
                logger.warning(f"Could not verify ElevenLabs quota (status {response.status_code}). Using OpenAI TTS.")
        except Exception as e:
            logger.warning(f"Error checking ElevenLabs quota: {e}. Using OpenAI TTS as fallback.")
    
    # Use ElevenLabs if quota is available, otherwise fallback to OpenAI
    if USE_ELEVENLABS:
        tts_instance = elevenlabs.TTS(voice_id=ELEVENLABS_VOICE_ID, api_key=ELEVEN_API_KEY)
    else:
        if not ELEVEN_API_KEY:
            logger.warning("ELEVEN_API_KEY not found - Using OpenAI TTS")
        tts_instance = openai.TTS(voice="alloy")  # Options: alloy, echo, fable, onyx, nova, shimmer
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        # Use ElevenLabs TTS with the specified voice and API key
        # Explicitly pass API key to ensure it's used correctly
        # You can also use OpenAI's TTS with openai.TTS() or Cartesia with cartesia.TTS()
        tts=tts_instance,
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
        agent.session = session
        
        # Track call start time
        agent.call_start_time = datetime.datetime.now()
        
        # Note: Transcripts are now captured from the conversation history
        # This provides both user and agent messages in chronological order
        
        # Wait before initial greeting (adjustable delay)
        # This gives the user time to say "hello" first, or ensures connection is stable
        if INITIAL_GREETING_DELAY > 0:
            logger.info(f"Waiting {INITIAL_GREETING_DELAY} seconds before initial greeting...")
            await asyncio.sleep(INITIAL_GREETING_DELAY)
        
        # Generate initial greeting - Lia's script opening
        # CRITICAL: Only say "Hey, {name}?" and then STOP - wait for their response
        await session.generate_reply(
            instructions=f"Say ONLY this: 'Hey, {customer_name}?' Then STOP COMPLETELY and wait for their response. Do not say anything else until they respond."
        )

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
