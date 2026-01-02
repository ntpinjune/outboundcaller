# How Google Calendar Integration Works

## Overview

The agent uses **direct Google Calendar API integration** (no webhooks or Make.com). When a customer wants to schedule an appointment during a call, the agent:

1. **Checks availability** in your Google Calendar
2. **Creates a calendar event** with a Google Meet link
3. **Sends an invite** to the customer's email automatically
4. **Tracks the appointment** for call results

## Architecture

```
Customer Call
    ↓
Agent asks: "What's easier for you, mornings or afternoons?"
    ↓
Customer suggests: "Tuesday at 2pm"
    ↓
Agent calls: checkAvailability("Tuesday at 2pm")
    ↓
Google Calendar API: Checks for conflicts
    ↓
Agent: "That time works perfectly" OR "Looks like the closest open time is..."
    ↓
Agent asks: "What's the best email to send the calendar invite to?"
    ↓
Customer provides email
    ↓
Agent calls: schedule_meeting(email, "Tuesday at 2pm", name)
    ↓
Google Calendar API: Creates event + Google Meet link
    ↓
Google Calendar: Automatically sends email invite to customer
    ↓
Agent: "I just sent that invite over. Let me know when you see it pop up?"
```

## Components

### 1. GoogleCalendar Class (`google_calendar.py`)

The `GoogleCalendar` class handles all Google Calendar operations:

#### Authentication
- Uses OAuth 2.0 with `credentials.json` (from Google Cloud Console)
- Stores tokens in `token.json` (auto-created after first auth)
- Automatically refreshes expired tokens
- **You're already authenticated** (token.json exists)

#### Methods

**`check_availability(start_time, end_time)`**
- Queries your Google Calendar for events in the time range
- Returns `True` if slot is free, `False` if busy
- Checks your primary calendar

**`get_next_available_time(preferred_time, duration_minutes=30)`**
- Finds the next available 30-minute slot
- Starts checking from preferred time, increments by 30 minutes
- Checks up to 24 hours ahead
- Returns the first available datetime

**`create_meet_event(attendee_email, start_time, summary)`**
- Creates a Google Calendar event (30 minutes duration)
- Adds Google Meet link automatically
- Adds customer as attendee
- Google Calendar **automatically sends email invite** to the customer
- Returns the Google Meet link

### 2. Agent Tools (`agent.py`)

The agent has two tools that customers interact with:

#### `checkAvailability(dateTime: str)`

**What it does:**
- Parses natural language dates/times ("Tuesday at 2pm", "tomorrow at 3pm", etc.)
- Converts to UTC datetime for Google Calendar API
- Checks if the time slot is available
- Returns availability status

**Example usage:**
- Customer: "Tuesday at 2pm"
- Agent calls: `checkAvailability("Tuesday at 2pm")`
- Google Calendar: Checks for conflicts at that time
- Agent responds: "That time works perfectly" OR suggests alternative

**Date parsing supports:**
- "Tuesday at 2pm"
- "tomorrow at 3pm"
- "next Monday at 10am"
- ISO format: "2024-01-15T14:00:00"
- Defaults to tomorrow at 2pm if parsing fails

#### `schedule_meeting(email: str, dateTime: str, name: str)`

**What it does:**
- Parses the date/time (same as checkAvailability)
- Creates Google Calendar event with Google Meet link
- Adds customer email as attendee
- Google Calendar automatically sends email invite
- Stores appointment info for call results

**Example usage:**
- Customer: "john@example.com"
- Agent calls: `schedule_meeting("john@example.com", "Tuesday at 2pm", "John Doe")`
- Google Calendar: Creates event + Meet link + sends email
- Agent: "I just sent that invite over..."

**Event details:**
- **Title**: "Landscaping Marketing Consultation"
- **Duration**: 30 minutes
- **Location**: Google Meet (with Meet link)
- **Attendees**: Customer's email
- **Timezone**: UTC (converted from PST)
- **Description**: "Conversation with your AI assistant."

## Flow During a Call

### Step 1: Customer Shows Interest
Customer says: "Yeah, I'm interested" or "Tell me more"

### Step 2: Agent Offers Appointment
Agent: "What's easier for you, mornings or afternoons?"

### Step 3: Customer Suggests Time
Customer: "Tuesday at 2pm" or "How about tomorrow afternoon?"

### Step 4: Check Availability
```
Agent internally calls:
  checkAvailability("Tuesday at 2pm")
    ↓
GoogleCalendar.check_availability()
    ↓
Queries Google Calendar API
    ↓
Returns: True (available) or False (busy)
```

**If available:**
- Agent: "That time works perfectly."

**If busy:**
- Agent calls `get_next_available_time()`
- Agent: "Ah okay — sorry about that. Looks like the closest open time is [next_time]. Would that work?"

### Step 5: Get Customer Email
Agent: "Okay, to lock that in... what's the best email to send the calendar invite to?"
Customer: "john@example.com"
Agent: "Just to make sure I don't mess it up... that was john@example.com. Is that right?"

### Step 6: Create Calendar Event
```
Agent internally calls:
  schedule_meeting("john@example.com", "Tuesday at 2pm", "John Doe")
    ↓
GoogleCalendar.create_meet_event()
    ↓
Creates event via Google Calendar API
    ↓
Google Calendar automatically:
  - Creates event in your calendar
  - Generates Google Meet link
  - Sends email invite to john@example.com
    ↓
Returns Google Meet link to agent
```

### Step 7: Confirm with Customer
Agent: "Okay, perfect... I just sent that invite over. Let me know when you see it pop up?"
*(Waits for customer response)*

Customer: "Yeah, I see it"
Agent: "Perfect."

### Step 8: Post-Booking Flow
Agent: "Okay, cool. Could you do me one quick favor and add it to your calendar right now? Google's been a little weird lately... and sometimes the meeting doesn't sync unless you hit accept."

Agent: "Alright, so I've got you down for [time]. Is there any reason at all you wouldn't be able to make that time?"

## Technical Details

### Authentication
- Uses Google OAuth 2.0
- Credentials stored in `credentials.json` (from Google Cloud Console)
- Access tokens stored in `token.json` (auto-refreshed)
- **Scope**: `https://www.googleapis.com/auth/calendar.events`

### API Calls
- All Google Calendar API calls are made **synchronously** in a thread pool
- This prevents blocking the async agent event loop
- Uses `ThreadPoolExecutor` to run sync Google API code

### Timezone Handling
- Agent works in PST (Pacific Standard Time)
- Dates/times are converted to UTC for Google Calendar API
- Events are created in UTC timezone
- Google Calendar automatically converts to user's timezone when displaying

### Error Handling
- If authentication fails → Raises error (you'll need to re-authenticate)
- If API call fails → Logs error, returns None (agent handles gracefully)
- If time slot is busy → Suggests next available time
- If date parsing fails → Defaults to tomorrow at 2pm

## Email Invites

**Google Calendar automatically sends email invites!**

When `create_meet_event()` is called:
1. Google Calendar creates the event
2. Adds the customer email as an attendee
3. **Automatically sends email invite** to the customer
4. Email includes:
   - Event title
   - Date and time
   - Google Meet link
   - Your calendar details

**No additional email setup needed!** Google handles everything.

## Integration Points

### With Agent Script
The agent follows this flow (from the "Lia" script):
1. **THE CLOSE**: Agent asks "What's easier for you, mornings or afternoons?"
2. **Step A**: Customer suggests time → `checkAvailability()`
3. **Step B**: Get email address
4. **Step C**: `schedule_meeting()` → Creates event + sends invite
5. **POST-BOOKING FLOW**: Confirms invite was received

### With Call Results
After the call, appointment info is saved:
- `appointment_scheduled`: True/False
- `appointment_time`: ISO datetime string
- `appointment_email`: Customer email
- Sent to Google Sheets (if configured)

## Testing

### Test Calendar Integration
```bash
python test_google_auth.py
```
This verifies authentication is working.

### Test During a Call
1. Start agent: `python agent.py dev`
2. Make a test call
3. During conversation, ask agent to schedule appointment
4. Check your Google Calendar - event should appear
5. Check customer email - invite should be received

## Key Features

✅ **Real-time availability checking** - Checks your calendar instantly  
✅ **Automatic email invites** - Google Calendar sends invites automatically  
✅ **Google Meet links** - Every event gets a Meet link  
✅ **Natural language parsing** - Understands "Tuesday at 2pm", "tomorrow", etc.  
✅ **Conflict detection** - Suggests alternatives if time is busy  
✅ **No external services** - Direct API integration, no webhooks needed  
✅ **Automatic token refresh** - Handles expired tokens automatically  

## Configuration

No additional configuration needed! Just:
1. ✅ `credentials.json` - Already have this
2. ✅ `token.json` - Already authenticated
3. ✅ Google Calendar API enabled in Google Cloud Console

The integration is **ready to use** - it will work automatically when customers want to schedule appointments!


