# SMS Text Message Setup for Calendar Invites

The agent now sends calendar invites via **text message** instead of email!

## Setup Required

### 1. Install Twilio Package

```bash
pip install -r requirements.txt
```

### 2. Add Twilio Credentials to `.env.local`

Add these three environment variables:

```bash
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890  # Your Twilio phone number (must include + and country code)
```

### 3. Get Twilio Credentials

1. Sign up at https://www.twilio.com/ (free trial available)
2. Get your Account SID and Auth Token from the Twilio Console
3. Get a phone number from Twilio (or use your existing one)
4. Add all three values to `.env.local`

## How It Works

1. **Phone Number Collection**: The agent asks if the number they're calling is the best one to text (or asks for a different number)

2. **Calendar Event Creation**: Creates a Google Calendar event with Google Meet link

3. **SMS Sending**: Sends a text message with:
   - Meeting time and date
   - Google Meet link to join the meeting

## Example SMS Message

```
Hi John! Your meeting is scheduled for 02:00 PM on Tuesday, January 07, 2025. Join here: https://meet.google.com/abc-defg-hij
```

## Fallback Behavior

- If Twilio credentials are not configured, the agent will still create the calendar event but won't send SMS
- The agent will log a warning and continue normally

## Testing

After adding your Twilio credentials:
1. Restart the agent
2. Make a test call
3. Schedule a meeting
4. Check your phone for the text message with the calendar invite!

