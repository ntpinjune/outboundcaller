
import asyncio
import os
from livekit import api
from dotenv import load_dotenv

load_dotenv(".env.local")

async def clear_queue():
    url = os.getenv("LIVEKIT_URL")
    key = os.getenv("LIVEKIT_API_KEY")
    secret = os.getenv("LIVEKIT_API_SECRET")

    if not url or not key or not secret:
        print("Error: LiveKit credentials not found in .env.local")
        return

    print(f"Connecting to {url}...")
    lkapi = api.LiveKitAPI(url, key, secret)

    try:
        print("Listing active rooms...")
        response = await lkapi.room.list_rooms(api.ListRoomsRequest())
        rooms = response.rooms

        if not rooms:
            print("No active rooms found. Queue is empty!")
            return

        print(f"Found {len(rooms)} active rooms. Clearing them now...")

        for room in rooms:
            print(f"Deleting room: {room.name} (SID: {room.sid})")
            try:
                await lkapi.room.delete_room(api.DeleteRoomRequest(room=room.name))
                print(f"✅ Deleted {room.name}")
            except Exception as e:
                print(f"❌ Failed to delete {room.name}: {e}")

        print("\nAll rooms cleared.")
    
    except Exception as e:
        print(f"Error communicating with LiveKit: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(clear_queue())
