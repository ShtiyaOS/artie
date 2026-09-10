
import os
from dotenv import load_dotenv
from supabase import create_client

# -- Setup --
load_dotenv()
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

# -- Main --
PROJECT_TITLE = "Demo — The Long Way Back"
print(f"Looking for project: '{PROJECT_TITLE}'")

# 1. Find the project
project_res = supabase.table("projects").select("project_id").eq("working_title", PROJECT_TITLE).limit(1).execute()
if not project_res.data:
    print("Demo project not found. Exiting.")
    exit()
project_id = project_res.data[0]["project_id"]
print(f"Found project_id: {project_id}")

# 2. Find the scene
scene_res = supabase.table("scenes").select("scene_id").eq("project_id", project_id).eq("sequence_order", 1).limit(1).execute()
if not scene_res.data:
    print("Scene 1 not found for demo project. Exiting.")
    exit()
scene_id = scene_res.data[0]["scene_id"]
print(f"Found scene_id: {scene_id}")

# 3. Find the take
take_res = supabase.table("takes").select("take_id").eq("scene_id", scene_id).limit(1).execute()
if not take_res.data:
    print("No take found for demo scene. Exiting.")
    exit()
take_id = take_res.data[0]["take_id"]
print(f"Found take_id: {take_id}")

# 4. Delete existing components for the take
print(f"Deleting existing components for take_id: {take_id}")
delete_res = supabase.table("script_components").delete().eq("take_id", take_id).execute()
print(f"Deleted {len(delete_res.data)} components.")

# 5. Insert the new seed components
print("Inserting new seed components...")
components_to_seed = [
    {"take_id": take_id, "sequence_order": 1, "comp_type": "SCENE_HEADING", "content": "INT. DINER - NIGHT"},
    {"take_id": take_id, "sequence_order": 2, "comp_type": "ACTION", "content": "A man sits alone with cold coffee."},
    {"take_id": take_id, "sequence_order": 3, "comp_type": "CHARACTER", "content": "MARLA"},
    {"take_id": take_id, "sequence_order": 4, "comp_type": "DIALOGUE", "content": "You said you'd stop coming here."},
]
insert_res = supabase.table("script_components").insert(components_to_seed).execute()
print(f"Inserted {len(insert_res.data)} new components.")

print("Cleanup complete.")
