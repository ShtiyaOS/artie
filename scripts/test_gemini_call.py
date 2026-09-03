import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

for key in ("GEMINI_TEXT_MODEL", "GEMINI_FAST_MODEL"):
    model = os.environ[key]
    r = client.models.generate_content(
        model=model,
        contents="Reply with exactly three words describing rain.",
    )
    print(f"{model}: {r.text.strip()}")
    if r.usage_metadata:
        print(f"  tokens in/out: {r.usage_metadata.prompt_token_count}/"
              f"{r.usage_metadata.candidates_token_count}")
