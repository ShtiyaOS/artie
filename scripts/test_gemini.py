import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

print("=== AVAILABLE MODELS ===")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    print(f"{m.name:60} {actions}")
