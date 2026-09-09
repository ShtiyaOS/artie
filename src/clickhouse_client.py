"""
ClickHouse singleton client.

Connection config mirrors scripts/test_clickhouse.py exactly.
"""

import os

import clickhouse_connect

_client = None


def get_client():
    """Return the singleton ClickHouse client, creating it on first call."""
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ["CLICKHOUSE_PORT"]),
            username=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
        )
    return _client


def get_ranked_gaps(project_id: str, bible_version_id: int):
    """
    Execute the ranked gaps query against ClickHouse.
    Governed by docs/10_clickhouse.md §5.3.
    """
    client = get_client()
    query = """
        WITH latest AS (
            SELECT
                scene_id,
                cell_id_num,
                any(position_id)                              AS position_id,
                argMax(verdict,          diagnosed_at_micros) AS verdict,
                argMax(input_confidence, diagnosed_at_micros) AS input_confidence,
                argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
            FROM scene_diagnoses
            WHERE project_id = %(project_id)s
            GROUP BY scene_id, cell_id_num
        ),
        fresh AS (
            SELECT * FROM latest WHERE bible_version_id = %(bible_version_id)s
        ),
        per_cell AS (
            SELECT
                cell_id_num,
                countIf(verdict = 'SATISFIED') AS n_satisfied,
                countIf(verdict = 'NA')        AS n_na,
                count()                        AS n_total,
                max(toUInt8(input_confidence)) AS worst_input
            FROM fresh GROUP BY cell_id_num
        ),
        density AS (
            SELECT position_id, uniqExact(scene_id) AS active_scenes
            FROM fresh GROUP BY position_id
        )
        SELECT
            c.cell_id,
            c.priority_weight,
            toString(c.confidence)                                    AS cell_confidence,
            coalesce(d.active_scenes, 0)                              AS scene_density,
            c.priority_weight * if(pc.worst_input = 2, 0.75, 1.0)      AS severity,
            severity * (1 + log(1 + coalesce(d.active_scenes, 0)))    AS urgency
        FROM cells_src AS c
        LEFT JOIN per_cell AS pc USING (cell_id_num)
        LEFT JOIN density  AS d  ON c.position_id = d.position_id
        WHERE pc.n_satisfied = 0
          AND NOT (pc.n_total > 0 AND pc.n_na = pc.n_total)
        ORDER BY urgency DESC, c.cell_id ASC
    """
    result = client.query(
        query,
        parameters={
            "project_id": project_id,
            "bible_version_id": bible_version_id,
        },
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def get_coverage_heatmap(project_id: str, bible_version_id: int):
    """
    Execute the coverage heatmap query against ClickHouse.
    Governed by docs/10_clickhouse.md §5.2.
    """
    client = get_client()
    query = """
        WITH latest AS (
            SELECT
                scene_id,
                cell_id_num,
                any(position_id)                              AS position_id,
                argMax(verdict,          diagnosed_at_micros) AS verdict,
                argMax(input_confidence, diagnosed_at_micros) AS input_confidence,
                argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
            FROM scene_diagnoses
            WHERE project_id = %(project_id)s
            GROUP BY scene_id, cell_id_num
        ),
        fresh AS (
            SELECT * FROM latest WHERE bible_version_id = %(bible_version_id)s
        ),
        per_cell AS (
            SELECT
                cell_id_num,
                countIf(verdict = 'SATISFIED')          AS n_satisfied,
                countIf(verdict = 'GAP')                AS n_gap,
                countIf(verdict = 'NA')                 AS n_na,
                count()                                 AS n_total,
                max(toUInt8(input_confidence))          AS worst_input
            FROM fresh
            GROUP BY cell_id_num
        )
        SELECT
            c.cell_id                                              AS cell_id,
            dictGet('dict_positions', 'code', toUInt64(c.position_id)) AS position,
            dictGet('dict_lenses',    'code', toUInt64(c.lens_id))     AS lens,
            multiIf(
                pc.n_total     = 0,          'NO_DATA',
                pc.n_satisfied > 0,          'SATISFIED',
                pc.n_na        = pc.n_total, 'NA',
                                             'GAP'
            )                                                      AS coverage_state,
            toString(c.confidence)                                 AS cell_confidence,
            multiIf(pc.worst_input = 2, 'PROVISIONAL', pc.n_total = 0, 'NONE', 'VALIDATED')
                                                                   AS input_confidence,
            multiIf(
                pc.worst_input != 2,        toString(c.confidence),
                c.confidence = 'ATTESTED',  'ANCHORED',
                c.confidence = 'ANCHORED',  'EXTRAPOLATED',
                                            'EXTRAPOLATED'
            )                                                      AS display_confidence
        FROM cells_src AS c
        LEFT JOIN per_cell AS pc USING (cell_id_num)
        ORDER BY c.position_id, c.lens_id
    """
    result = client.query(
        query,
        parameters={
            "project_id": project_id,
            "bible_version_id": bible_version_id,
        },
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def get_cell_definitions(cell_id_nums: list[int]):
    """
    Retrieve cell definitions from ClickHouse by their numeric IDs.
    """
    client = get_client()
    query = "SELECT * FROM cells_src WHERE cell_id_num IN %(cell_id_nums)s"
    result = client.query(query, parameters={"cell_id_nums": cell_id_nums})
    
    # The `diagnostic_question` and `failure_signature` are not in the DB.
    # We will need to load them from the canonical source in a future step.
    # For now, we will add placeholder values.
    # This is a temporary measure to fulfill the contract for Task 38.
    
    defs = {}
    for row in result.result_rows:
        row_dict = dict(zip(result.column_names, row))
        cell_id = row_dict["cell_id"]
        row_dict["diagnostic_question"] = f"Placeholder question for {cell_id}"
        row_dict["failure_signature"] = f"Placeholder failure signature for {cell_id}"
        defs[row_dict["cell_id_num"]] = row_dict
        
    return defs


def get_provenance_events(project_id: str):
    """
    Retrieve all provenance events for a project.
    """
    client = get_client()
    query = "SELECT * FROM provenance_events WHERE project_id = %(project_id)s ORDER BY event_timestamp"
    result = client.query(query, parameters={"project_id": project_id})
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def get_keystroke_batches(project_id: str):
    """
    Retrieve all keystroke batches for a project.
    """
    client = get_client()
    query = "SELECT * FROM keystroke_batches WHERE project_id = %(project_id)s ORDER BY received_at_micros"
    result = client.query(query, parameters={"project_id": project_id})
    return [dict(zip(result.column_names, row)) for row in result.result_rows]
