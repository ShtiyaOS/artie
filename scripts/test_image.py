import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
model = os.environ["GEMINI_IMAGE_MODEL"]

prompt = (
    "A photorealistic medium shot of a tired woman in her early thirties, "
    "dark hair pulled back, worn denim jacket, sitting alone in a corner booth "
    "of an American diner at night, both hands around a cold mug of coffee, "
    "gazing down. Neon light spills through a rain-streaked window behind her. "
    "Shot at eye level with a 50mm lens, shallow depth of field, low-key lighting. "
    "Cinematic."
)

r = client.models.generate_content(model=model, contents=prompt)

cand = r.candidates[0]
print("finish_reason:", cand.finish_reason)
print("prompt_feedback:", r.prompt_feedback)

saved = False
for part in cand.content.parts:
    if getattr(part, "text", None):
        print("TEXT:", part.text[:300])
    if getattr(part, "inline_data", None):
        with open("static/test_frame.png", "wb") as f:
            f.write(part.inline_data.data)
        print("Saved static/test_frame.png",
              len(part.inline_data.data), "bytes",
              part.inline_data.mime_type)
        saved = True

if not saved:
    print("No image returned.")

if r.usage_metadata:
    print("usage:", r.usage_metadata)
