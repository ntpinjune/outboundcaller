#!/usr/bin/env python3
"""Test script to verify Google Calendar integration is working."""

import asyncio
import datetime
from google_calendar import GoogleCalendar
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_calendar_integration():
    print("=" * 60)
    print("Google Calendar Integration Test")
    print("=" * 60)
    
    try:
        # Create GoogleCalendar instance
        calendar = GoogleCalendar()
        print("\n✓ GoogleCalendar instance created")
        
        # Test 1: Check authentication
        print("\n[Test 1] Checking authentication...")
        calendar._ensure_authenticated()
        if calendar.creds and calendar.creds.valid:
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
            return
        
        # Test 2: Check availability for a future time
        print("\n[Test 2] Testing check_availability...")
        test_time = datetime.datetime.now() + datetime.timedelta(hours=2)
        test_end = test_time + datetime.timedelta(minutes=30)
        
        # Ensure UTC timezone
        if test_time.tzinfo is None:
            test_time = test_time.replace(tzinfo=datetime.timezone.utc)
        if test_end.tzinfo is None:
            test_end = test_end.replace(tzinfo=datetime.timezone.utc)
        
        is_available = await calendar.check_availability(test_time, test_end)
        print(f"✓ Availability check completed: {'Available' if is_available else 'Busy'}")
        
        # Test 3: Get next available time
        print("\n[Test 3] Testing get_next_available_time...")
        next_available = await calendar.get_next_available_time(test_time)
        print(f"✓ Next available time: {next_available}")
        
        # Test 4: Create a test event (optional - comment out if you don't want to create events)
        print("\n[Test 4] Testing create_meet_event...")
        test_email = "test@example.com"  # Change this to your email for testing
        event_time = datetime.datetime.now() + datetime.timedelta(hours=3)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=datetime.timezone.utc)
        
        meet_link = await calendar.create_meet_event(
            attendee_email=test_email,
            start_time=event_time,
            summary="Test Meeting from AI Agent"
        )
        
        if meet_link:
            print(f"✅ Event created successfully!")
            print(f"✓ Google Meet link: {meet_link}")
        else:
            print("❌ Failed to create event")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_calendar_integration())

