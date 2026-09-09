
import argparse
import os
import sys

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clickhouse_client import get_client as get_clickhouse_client
from src.supabase_client import get_client as get_supabase_client

def verify_manifest(project_id: str):
    """
    Verify that the content hash of the script components in Supabase
    matches the hash of the keystroke batches in ClickHouse.
    """
    print(f"Verifying manifest for project {project_id}...")

    # Get the Supabase content hashes
    supabase = get_supabase_client()
    response = supabase.rpc("get_all_components_for_project", {"prj_id": project_id}).execute()
    if not response.data:
        print("No script components found in Supabase.")
        return

    supabase_hashes = {item['component_id']: item['content_hash'] for item in response.data}
    print(f"Found {len(supabase_hashes)} script components in Supabase.")

    # Get the ClickHouse content hashes
    clickhouse = get_clickhouse_client()
    query = f"""
    SELECT
        component_id,
        argMax(content_hash, ts_end_micros) AS last_content_hash
    FROM
        keystroke_batches
    WHERE
        project_id = '{project_id}'
    GROUP BY
        component_id
    """
    result = clickhouse.query(query)
    clickhouse_hashes = {row[0]: row[1] for row in result.result_rows}
    print(f"Found {len(clickhouse_hashes)} script components in ClickHouse.")

    # Compare the hashes
    mismatches = []
    for component_id, supabase_hash in supabase_hashes.items():
        if supabase_hash is None:
            continue
        clickhouse_hash = clickhouse_hashes.get(component_id)
        if supabase_hash != clickhouse_hash:
            mismatches.append((component_id, supabase_hash, clickhouse_hash))

    if not mismatches:
        print("Manifest verified successfully. All content hashes match.")
    else:
        print(f"Found {len(mismatches)} mismatches:")
        for component_id, supabase_hash, clickhouse_hash in mismatches:
            print(f"  Component {component_id}:")
            print(f"    Supabase hash: {supabase_hash}")
            print(f"    ClickHouse hash: {clickhouse_hash}")

if __name__ == "__main__":
    # This script is designed to be run from the command line.
    # It verifies that the content hash of the script components in Supabase
    # matches the hash of the keystroke batches in ClickHouse.
    #
    # To run this script:
    # python scripts/verify_manifest.py <project_id>
    #
    # It requires the following environment variables to be set:
    # - SUPABASE_URL
    # - SUPABASE_SERVICE_ROLE_KEY
    # - CLICKHOUSE_HOST
    # - CLICKHOUSE_PORT
    # - CLICKHOUSE_USER
    # - CLICKHOUSE_PASSWORD
    
    parser = argparse.ArgumentParser(description="Verify manifest.")
    parser.add_argument("project_id", help="The project ID to verify.")
    args = parser.parse_args()

    verify_manifest(args.project_id)
