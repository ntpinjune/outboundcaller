#!/usr/bin/env python3
"""Test script to verify agent's Google Calendar tools work with various date/time formats."""

import asyncio
import datetime
import sys
import os

# Add the current directory to the path so we can import agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import OutboundCaller
from livekit.agents import RunContext
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MockRunContext:
    """Mock RunContext for testing"""
    def __init__(self):
        self.session = None
    
    async def wait_for_playout(self):
        """Mock wait_for_playout"""
        pass

class MockParticipant:
    """Mock participant for testing"""
    def __init__(self):
        self.identity = "+12095539289"

async def test_agent_calendar_tools():
    """Test the agent's calendar tools with various date/time formats"""
    
    print("=" * 70)
    print("Testing Agent Google Calendar Tools")
    print("=" * 70)
    
    # Create a mock agent instance
    dial_info = {
        "phone_number": "+12095539289",
        "name": "Test Customer",
        "row_id": "test-1"
    }
    
    try:
        agent = OutboundCaller(
            name="Test Customer",
            appointment_time="",
            dial_info=dial_info
        )
        
        # Set a mock participant
        agent.set_participant(MockParticipant())
        
        # Create mock context
        ctx = MockRunContext()
        
        print("\n[Test 1] Testing checkAvailability with 'Tuesday at 2pm'")
        print("-" * 70)
        try:
            result = await agent.checkAvailability(ctx, "Tuesday at 2pm")
            print(f"✅ checkAvailability('Tuesday at 2pm') succeeded")
            print(f"   Result: {result}")
            if isinstance(result, dict):
                if result.get("available"):
                    print(f"   ✓ Time is available")
                else:
                    print(f"   ✓ Time is busy, next available: {result.get('next_available_time', 'N/A')}")
        except Exception as e:
            print(f"❌ checkAvailability failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n[Test 2] Testing checkAvailability with 'tomorrow at 3pm'")
        print("-" * 70)
        try:
            result = await agent.checkAvailability(ctx, "tomorrow at 3pm")
            print(f"✅ checkAvailability('tomorrow at 3pm') succeeded")
            print(f"   Result: {result}")
        except Exception as e:
            print(f"❌ checkAvailability failed: {e}")
        
        print("\n[Test 3] Testing checkAvailability with 'next week Monday at 10am'")
        print("-" * 70)
        try:
            result = await agent.checkAvailability(ctx, "next week Monday at 10am")
            print(f"✅ checkAvailability('next week Monday at 10am') succeeded")
            print(f"   Result: {result}")
        except Exception as e:
            print(f"❌ checkAvailability failed: {e}")
        
        print("\n[Test 4] Testing schedule_meeting with email and time")
        print("-" * 70)
        test_email = "test@example.com"  # Change this to your email for actual testing
        try:
            result = await agent.schedule_meeting(
                ctx,
                email=test_email,
                dateTime="Tuesday at 2pm",
                name="Test Customer"
            )
            print(f"✅ schedule_meeting succeeded")
            print(f"   Email: {test_email}")
            print(f"   Time: Tuesday at 2pm")
            print(f"   Result: {result}")
            if "error" in str(result).lower() or "failed" in str(result).lower():
                print(f"   ⚠️  Warning: Result suggests an error")
            else:
                print(f"   ✓ Calendar event should be created")
        except Exception as e:
            print(f"❌ schedule_meeting failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n[Test 5] Testing schedule_meeting with spelled-out email")
        print("-" * 70)
        try:
            result = await agent.schedule_meeting(
                ctx,
                email="i t z n t p at Gmail dot co",
                dateTime="tomorrow at 2pm",
                name="Test Customer"
            )
            print(f"✅ schedule_meeting with spelled-out email succeeded")
            print(f"   Input email: 'i t z n t p at Gmail dot co'")
            print(f"   Result: {result}")
            # Check if email was parsed correctly
            if "itzntp@gmail.com" in str(result) or "itzntp@gmail.com" in str(agent.appointment_email or ""):
                print(f"   ✓ Email parsing works correctly")
            else:
                print(f"   ⚠️  Email parsing may not have worked")
        except Exception as e:
            print(f"❌ schedule_meeting failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n[Test 6] Testing various date/time formats")
        print("-" * 70)
        test_formats = [
            "Tuesday at 2pm",
            "tomorrow at 3pm",
            "next Monday at 10am",
            "Friday at 4pm",
            "2026-01-15 14:00:00"
        ]
        
        for date_format in test_formats:
            try:
                result = await agent.checkAvailability(ctx, date_format)
                print(f"✅ '{date_format}' → Parsed successfully")
            except Exception as e:
                print(f"❌ '{date_format}' → Failed: {e}")
        
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        print("✅ If all tests passed, the agent's calendar tools are working!")
        print("⚠️  If any tests failed, check the error messages above.")
        print("\nNext steps:")
        print("1. Check your Google Calendar to see if test events were created")
        print("2. Monitor agent logs during real calls to verify tools are called")
        print("3. If tools aren't called during calls, the issue is with the LLM, not the tools")
        
    except Exception as e:
        print(f"\n❌ Failed to create agent instance: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_calendar_tools())

