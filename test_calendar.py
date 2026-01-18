import asyncio
import logging
from google_calendar import GoogleCalendar
from datetime import datetime, timedelta

# Monitor log output
logging.basicConfig(level=logging.INFO)

async def test():
    print("Initializing GoogleCalendar...")
    cal = GoogleCalendar()
    
    print("Checking availability for tomorrow...")
    tomorrow = datetime.now() + timedelta(days=1)
    
    # We just want to trigger authentication check
    try:
        available = await cal.check_availability(tomorrow, tomorrow + timedelta(minutes=30))
        print(f"Availability check result: {available}")
        print("SUCCESS: Google Calendar is linked and authenticated!")
    except Exception as e:
        print(f"FAILURE: Error checking availability: {e}")

if __name__ == "__main__":
    asyncio.run(test())
