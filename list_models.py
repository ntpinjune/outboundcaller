
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(dotenv_path=".env.local")

api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)

for model in client.models.list():
    print(f"Model: {model.name}, Supported Actions: {model.supported_actions}")
