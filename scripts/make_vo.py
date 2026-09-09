import os, base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SCRIPT = """This is Artie Spiegel. An AI showrunner that runs the process while the writer keeps sole authorship.

Here's the workbench. Screenplay components format as you type. Press Enter and it moves to the next likely element. Character cue, dialogue, back again. The writer never opens a menu.

Everything the writer types is captured as a hash-chained keystroke record. Not the characters. Just the deltas, and a chain of hashes that proves the text grew by typing.

Now the part that matters.

Before Artie speaks, he deliberates. Two opposed positions, each with a strength. Expansion says hold it back, weight two. Restriction says raise it now, weight four. Synthesis picks: raise the finding at cell X 06 Y 2, hold the one at X 03 Y 1, and choose a register.

That trace is stored in the provenance ledger. It's evidence. Because the agent you're talking to has never read your screenplay.

Artie receives structured findings. The Script Supervisor reads the text. The backend strips every prose field before anything reaches Artie. His payload has no field for it. That's not a policy. That's the wiring.

Every scene is scored against a seventy-two cell matrix. Twelve narrative positions, six craft lenses, anchored in published corpora of film structure. The confidence gradient is visible. The matrix knows where it's weak, and says so.

At export you get the screenplay, and an authorship manifest. Composition record. Hash chain verification. Every agent action with counts. And the statement that no agent supplied screenplay text, backed by an audit of every payload.

Gemini on Cloud Run. ClickHouse for the matrix and the ledger. Confluent between them. Built with IBM Bob.

It will not write your scene. That's the point."""

resp = client.models.generate_content(
    model="models/gemini-2.5-flash-preview-tts",
    contents=SCRIPT,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        ),
    ),
)

data = resp.candidates[0].content.parts[0].inline_data.data
open("vo.pcm", "wb").write(data)
print("wrote vo.pcm", len(data), "bytes")
