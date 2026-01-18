import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv(".env.local", override=True)

async def test_slack():
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    print(f"Testing Webhook URL: {webhook_url}")
    
    if not webhook_url:
        print("ERROR: SLACK_WEBHOOK_URL not found in environment.")
        return

    message = "🎉 **Test Notification** \nThis is a test message from the Outbound Caller Agent to verify Slack integration."
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {"text": message}
            print("Sending request to Slack...")
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            
            if response.status_code == 200:
                print("✅ Slack notification sent successfully!")
            else:
                print("❌ Failed to send Slack notification.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_slack())
