# How to Test if Calendar Integration Works

## Quick Test Steps

### 1. Start the Agent

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python agent.py dev
```

You should see:
```
✓ Agent connecting to LiveKit
✓ Waiting for dispatches
✓ No errors
```

### 2. Make a Test Call

**Option A: Using dispatch_calls.py (if Google Sheets is configured)**
```bash
# In a new terminal
python dispatch_calls.py
```

**Option B: Using LiveKit CLI directly**
```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller-dev \
  --metadata '{"phone_number": "+1YOUR_PHONE_NUMBER", "name": "Test User"}'
```

Replace `+1YOUR_PHONE_NUMBER` with your actual phone number for testing.

### 3. During the Call - Test Calendar Scheduling

When the agent asks "What's easier for you, mornings or afternoons?", respond with:
- **"Tuesday at 2pm"** or **"tomorrow at 3pm"**

Then when asked for email, provide a real email address (where you can check for the calendar invite).

### 4. Check the Logs

**Look for these log messages in the agent terminal:**

#### ✅ Success Indicators:

1. **checkAvailability was called:**
   ```
   INFO outbound-caller - Checking availability for Tuesday at 2pm
   ```

2. **schedule_meeting was called:**
   ```
   INFO outbound-caller - scheduling meeting for your-email@example.com at Tuesday at 2pm
   ```

3. **Google Calendar event created:**
   ```
   INFO google-calendar - Event created: https://calendar.google.com/calendar/...
   ```

4. **No circular wait errors:**
   ```
   # Should NOT see this error:
   # RuntimeError: cannot call SpeechHandle.wait_for_playout()...
   ```

5. **end_call works:**
   ```
   INFO outbound-caller - ending the call for +1...
   # No errors after this
   ```

#### ❌ Failure Indicators:

1. **Tools not called:**
   - No "Checking availability for..." log
   - No "scheduling meeting for..." log
   - Agent just says it scheduled something without logs

2. **Circular wait error:**
   ```
   ERROR livekit.agents - exception occurred while executing tool
   RuntimeError: cannot call SpeechHandle.wait_for_playout()...
   ```

3. **Google Calendar errors:**
   ```
   ERROR google-calendar - An error occurred: ...
   ```

### 5. Verify Calendar Event Created

**Check your Google Calendar:**
1. Go to https://calendar.google.com
2. Look for an event titled: "Landscaping Marketing Consultation with Test User"
3. Check the date/time matches what you scheduled
4. Verify it has a Google Meet link

**Check the email:**
1. Check the email inbox you provided during the call
2. Look for a Google Calendar invite email
3. The invite should include:
   - Event details
   - Google Meet link
   - Your calendar as the organizer

### 6. Verify Call Results Updated (if using Google Sheets)

If you're using `dispatch_calls.py` with Google Sheets:
1. Open your Google Sheet
2. Find the row for your test number
3. Check that:
   - Status = "completed"
   - Appointment_time = (the time you scheduled)
   - Appointment_email = (the email you provided)
   - Transcript = (conversation transcript)

---

## Complete Test Flow Example

```
1. Start agent: python agent.py dev
2. Make call: python dispatch_calls.py (or LiveKit CLI)
3. Answer phone
4. Agent: "Hey, Test User?"
5. You: "Yeah?"
6. Agent: [goes through script]
7. Agent: "What's easier for you, mornings or afternoons?"
8. You: "Tuesday at 2pm"
9. [CHECK LOG: Should see "Checking availability for Tuesday at 2pm"]
10. Agent: "That time works perfectly. What's your email?"
11. You: "test@example.com"
12. Agent: "Just to make sure... that was test@example.com. Is that right?"
13. You: "Yes"
14. [CHECK LOG: Should see "scheduling meeting for test@example.com at Tuesday at 2pm"]
15. [CHECK LOG: Should see "Event created: https://calendar.google.com/..."]
16. Agent: "Perfect! I've scheduled your meeting..."
17. Agent: [continues with post-booking flow]
18. Agent: [ends call]
19. [CHECK LOG: Should see "ending the call" with NO errors]
20. [CHECK CALENDAR: Event should appear]
21. [CHECK EMAIL: Invite should be received]
```

---

## What Success Looks Like

### In the Logs:
```
INFO outbound-caller - Checking availability for Tuesday at 2pm
INFO google-calendar - Refreshing expired credentials...
INFO google-calendar - Credentials refreshed successfully
INFO outbound-caller - scheduling meeting for test@example.com at Tuesday at 2pm
INFO google-calendar - Event created: https://calendar.google.com/calendar/event?eid=...
INFO outbound-caller - ending the call for +1...
INFO outbound-caller - Call results updated in Google Sheets: completed
```

### In Your Google Calendar:
- ✅ Event titled "Landscaping Marketing Consultation with Test User"
- ✅ Scheduled for the correct date/time
- ✅ Has Google Meet link
- ✅ Has test@example.com as attendee

### In Your Email:
- ✅ Google Calendar invite received
- ✅ Contains event details
- ✅ Contains Google Meet link
- ✅ Can accept/decline the invite

---

## Troubleshooting

### If tools aren't being called:

1. **Check agent is restarted:**
   ```bash
   # Stop the agent (Ctrl+C)
   # Restart it
   python agent.py dev
   ```

2. **Check logs for tool execution:**
   - Look for "executing tool" messages
   - Check for any errors before tool calls

3. **Verify instructions:**
   - The agent should have the updated instructions with "MANDATORY" language
   - Check that tools are documented in the prompt

### If calendar events aren't created:

1. **Check Google Calendar authentication:**
   ```bash
   python test_google_auth.py
   ```
   Should show: ✅ Authentication successful

2. **Check logs for Google Calendar errors:**
   - Look for `ERROR google-calendar` messages
   - Check if credentials expired

3. **Verify token.json exists:**
   ```bash
   ls -la token.json
   ```

### If end_call still has errors:

1. **Verify the fix was applied:**
   ```bash
   grep -n "ctx.wait_for_playout" agent.py
   ```
   Should show line 338

2. **Check for any other wait_for_playout calls:**
   ```bash
   grep -n "wait_for_playout" agent.py
   ```
   Should only show `ctx.wait_for_playout()` (not `current_speech.wait_for_playout()`)

---

## Quick Verification Commands

**Check if fixes are in place:**
```bash
# Check end_call fix
grep -A 2 "async def end_call" agent.py | grep "ctx.wait_for_playout"

# Check for mandatory tool instructions
grep -i "mandatory.*checkAvailability" agent.py

# Check for mandatory schedule_meeting instructions
grep -i "mandatory.*schedule_meeting" agent.py
```

All three should return results if fixes are applied.


