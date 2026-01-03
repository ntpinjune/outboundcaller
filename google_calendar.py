import os.path
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger("google-calendar")

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

class GoogleCalendar:
    def __init__(self):
        self.creds = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._authenticated = False
    
    def _ensure_authenticated(self):
        """Ensure we have valid credentials, prompting for OAuth if needed."""
        if self._authenticated and self.creds and self.creds.valid:
            return
        
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            try:
                self.creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load token.json: {e}")
                self.creds = None
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    logger.info("Refreshing expired credentials...")
                    self.creds.refresh(Request())
                    logger.info("Credentials refreshed successfully")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    self.creds = None
            
            if not self.creds or not self.creds.valid:
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError(
                        "credentials.json not found. Please download it from Google Cloud Console. "
                        "Go to: https://console.cloud.google.com/apis/credentials"
                    )
                
                logger.info("Starting OAuth flow. A browser window should open...")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "credentials.json", SCOPES
                    )
                    logger.info("Opening browser for Google authentication...")
                    self.creds = flow.run_local_server(port=0)
                    logger.info("Authentication successful!")
                except Exception as e:
                    logger.error(f"OAuth flow failed: {e}")
                    raise RuntimeError(
                        f"Failed to authenticate with Google. Error: {e}\n"
                        "Make sure credentials.json is valid and you have internet access."
                    )
            
            # Save the credentials for the next run
            try:
                with open("token.json", "w") as token:
                    token.write(self.creds.to_json())
                    logger.info("Credentials saved to token.json")
            except Exception as e:
                logger.warning(f"Failed to save token.json: {e}")
        
        self._authenticated = True

    async def create_meet_event(self, attendee_email: str, start_time: datetime.datetime, summary: str = "Meeting with AI Agent"):
        """Creates a Google Calendar event with a Google Meet link."""
        def _create_event_sync():
            """Synchronous helper function to create the event."""
            # Ensure we're authenticated before making API calls
            self._ensure_authenticated()
            service = build("calendar", "v3", credentials=self.creds)

            end_time = start_time + datetime.timedelta(minutes=30)

            event = {
                "summary": summary,
                "location": "Google Meet",
                "description": "Conversation with your AI assistant.",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                },
                "attendees": [
                    {"email": attendee_email},
                ],
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"meet-{int(datetime.datetime.now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }

            # Insert event with sendUpdates to ensure email invite is sent
            return service.events().insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all",  # Send email invites to all attendees
            ).execute()

        try:
            # Run the synchronous Google API call in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            event = await loop.run_in_executor(self._executor, _create_event_sync)

            logger.info(f"Event created: {event.get('htmlLink')}")
            return event.get("hangoutLink")

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return None
        except Exception as error:
            logger.error(f"An unexpected error occurred: {error}")
            return None
    
    async def check_availability(self, start_time: datetime.datetime, end_time: datetime.datetime) -> bool:
        """Check if a time slot is available (no conflicting events).
        
        Args:
            start_time: Start of the time slot to check
            end_time: End of the time slot to check
            
        Returns:
            True if the time slot is available (no conflicts), False otherwise
        """
        def _check_availability_sync():
            """Synchronous helper function to check availability."""
            self._ensure_authenticated()
            service = build("calendar", "v3", credentials=self.creds)
            
            # Query for events in the time range
            # Ensure times are in UTC and properly formatted for Google Calendar API
            if start_time.tzinfo is None:
                start_time_utc = start_time.replace(tzinfo=datetime.timezone.utc)
            else:
                start_time_utc = start_time.astimezone(datetime.timezone.utc)
            
            if end_time.tzinfo is None:
                end_time_utc = end_time.replace(tzinfo=datetime.timezone.utc)
            else:
                end_time_utc = end_time.astimezone(datetime.timezone.utc)
            
            # Format as RFC3339 (Google Calendar API requires this format)
            time_min = start_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            time_max = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            # If there are any events in this time range, the slot is not available
            return len(events) == 0
        
        try:
            loop = asyncio.get_event_loop()
            is_available = await loop.run_in_executor(self._executor, _check_availability_sync)
            return is_available
        except Exception as error:
            logger.error(f"Error checking availability: {error}")
            return False  # Assume unavailable on error
    
    async def get_next_available_time(self, preferred_time: datetime.datetime, duration_minutes: int = 30) -> datetime.datetime:
        """Find the next available time slot after a preferred time.
        
        Args:
            preferred_time: The preferred start time
            duration_minutes: Duration of the meeting in minutes
            
        Returns:
            The next available datetime
        """
        def _get_next_available_sync():
            """Synchronous helper function to find next available time."""
            self._ensure_authenticated()
            service = build("calendar", "v3", credentials=self.creds)
            
            # Start checking from preferred time, increment by 30 minutes
            check_time = preferred_time
            max_attempts = 48  # Check up to 24 hours ahead
            
            for _ in range(max_attempts):
                end_check = check_time + datetime.timedelta(minutes=duration_minutes)
                
                # Ensure times are in UTC and properly formatted
                if check_time.tzinfo is None:
                    check_time_utc = check_time.replace(tzinfo=datetime.timezone.utc)
                else:
                    check_time_utc = check_time.astimezone(datetime.timezone.utc)
                
                if end_check.tzinfo is None:
                    end_check_utc = end_check.replace(tzinfo=datetime.timezone.utc)
                else:
                    end_check_utc = end_check.astimezone(datetime.timezone.utc)
                
                # Format as RFC3339
                time_min = check_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                time_max = end_check_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                events_result = service.events().list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime"
                ).execute()
                
                events = events_result.get("items", [])
                if len(events) == 0:
                    # Found an available slot
                    return check_time
                
                # Move to next 30-minute slot
                check_time += datetime.timedelta(minutes=30)
            
            # If no slot found, return the original preferred time + 24 hours
            return preferred_time + datetime.timedelta(hours=24)
        
        try:
            loop = asyncio.get_event_loop()
            next_available = await loop.run_in_executor(self._executor, _get_next_available_sync)
            return next_available
        except Exception as error:
            logger.error(f"Error getting next available time: {error}")
            # Fallback: return preferred time + 1 hour
            return preferred_time + datetime.timedelta(hours=1)
