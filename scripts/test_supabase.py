import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

print("Client created for:", os.environ["SUPABASE_URL"])

# Round-trip against a scratch table
try:
    client.table("_artie_smoke").insert({"note": "hello"}).execute()
    rows = client.table("_artie_smoke").select("*").execute()
    print("Round-trip OK:", rows.data)
except Exception as e:
    print("Table not found yet (expected before schema):", type(e).__name__)
    print("Connection itself is fine if the error mentions the missing table.")
