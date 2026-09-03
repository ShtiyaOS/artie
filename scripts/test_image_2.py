import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
model = os.environ["GEMINI_IMAGE_MODEL"]

# Persistent character block — copied verbatim between scenes, per the brief's
# descriptive-persistence guidance. Only the action and setting change.
SARAH = ("Sarah, a tired woman in her early thirties, dark hair pulled back, "
         "worn denim jacket over a grey t-shirt, a small scar above her left eyebrow")

TESTS = [
    ("thin",
     "A cinematic frame. INT. OFFICE - DAY. He waits."),
    ("consistency",
     f"A photorealistic wide shot of {SARAH}, standing at the end of a "
     "hospital corridor at night, holding a folded piece of paper, looking "
     "toward a closed door. Harsh overhead fluorescent light. Shot at eye "
     "level with a 35mm lens. Cinematic."),
]

for name, prompt in TESTS:
    print(f"\n{'='*60}\n{name}\n{'='*60}")
    r = client.models.generate_content(model=model, contents=prompt)
    cand = r.candidates[0]
    print("finish_reason:", cand.finish_reason)

    for part in cand.content.parts:
        if getattr(part, "text", None):
            print("TEXT:", part.text[:400])
        if getattr(part, "inline_data", None):
            path = f"static/test_{name}.jpg"
            with open(path, "wb") as f:
                f.write(part.inline_data.data)
            print("Saved", path, len(part.inline_data.data), "bytes")

    u = r.usage_metadata
    print(f"tokens: prompt={u.prompt_token_count} thoughts={u.thoughts_token_count} "
          f"total={u.total_token_count}")
