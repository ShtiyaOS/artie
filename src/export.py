"""
Export script to Fountain, PDF, and FDX.

docs/14_editor.md §12 — Export.
"""

import hashlib
from datetime import date

import hashlib
import io
from datetime import date

import screenplain.parsers.fountain as f
import screenplain.export.pdf as pdf
import screenplain.export.fdx as fdx
from screenplain.types import Screenplay

from src.blueprint import build_title_page
from src.fountain.emit import emit_fountain
from src.supabase_client import get_client as get_supabase
from src.confluent_producer import publish_event

def export_script(project_id: str, writer_name: str, format: str) -> bytes:
    """
    Export the final cut of a script to the specified format.
    """
    # 1. Get the title from the blueprint.
    supabase = get_supabase()
    try:
        title_res = supabase.table("bible_slots").select("value").eq("project_id", project_id).eq("slot_id", "S13").execute()
        title = title_res.data[0]["value"] if title_res.data else "Untitled"
    except Exception:
        title = "Untitled"

    # 2. Get the final cut takes.
    final_cut_res = supabase.rpc("get_final_cut_for_project", {"prj_id": project_id}).execute()
    if not final_cut_res.data:
        # No final cut takes found, return an empty document.
        return b""
    
    components = final_cut_res.data

    # 3. Assemble the Fountain document.
    title_page = build_title_page(title=title, writer_name=writer_name)
    fountain_doc = title_page + "\n\n" + emit_fountain(components)

    # 4. Convert to the desired format using screenplain.
    if format.lower() == "fountain":
        output_bytes = fountain_doc.encode("utf-8")
    else:
        script: Screenplay = f.parse(fountain_doc)
        buffer = io.BytesIO()
        if format.lower() == "pdf":
            pdf.export(script, buffer)
        elif format.lower() == "fdx":
            fdx.export(script, buffer)
        else:
            # Should not happen with proper validation at the API layer.
            return b""
        output_bytes = buffer.getvalue()

    # 5. Emit the SCRIPT_EXPORTED event.
    content_hash = hashlib.sha256(fountain_doc.encode("utf-8")).hexdigest()
    publish_event(
        event_type="SCRIPT_EXPORTED",
        actor="human",
        payload={
            "format": format.upper(),
            "content_hash": content_hash,
        },
        project_id=project_id,
    )

    return output_bytes
