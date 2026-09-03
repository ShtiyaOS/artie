import os
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=int(os.environ["CLICKHOUSE_PORT"]),
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=True,
)

P = {"project": "4f27d81a-6d0e-4361-b1e1-e137c6888c3a", "version": 5}

LATEST = """
WITH latest AS (
    SELECT scene_id, cell_id_num,
           any(position_id) AS position_id,
           argMax(verdict, diagnosed_at_micros) AS verdict,
           argMax(input_confidence, diagnosed_at_micros) AS input_confidence,
           argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
    FROM scene_diagnoses
    WHERE project_id = {project:UUID}
    GROUP BY scene_id, cell_id_num
),
fresh AS (SELECT * FROM latest WHERE bible_version_id = {version:UInt32})
"""

Q1 = LATEST + """,
per_cell AS (
    SELECT cell_id_num,
           countIf(verdict = 'SATISFIED') AS n_satisfied,
           countIf(verdict = 'NA') AS n_na,
           count() AS n_total,
           max(toUInt8(input_confidence)) AS worst_input
    FROM fresh GROUP BY cell_id_num
)
SELECT c.cell_id,
       multiIf(pc.n_total = 0, 'NO_DATA',
               pc.n_satisfied > 0, 'SATISFIED',
               pc.n_na = pc.n_total, 'NA',
               'GAP') AS coverage_state,
       toString(c.confidence) AS cell_confidence,
       multiIf(pc.n_total = 0, 'NONE',
               pc.worst_input = 2, 'PROVISIONAL',
               'VALIDATED') AS input_confidence
FROM cells_src AS c
LEFT JOIN per_cell AS pc USING (cell_id_num)
ORDER BY c.position_id, c.lens_id
"""

Q2 = LATEST + """,
per_cell AS (
    SELECT cell_id_num,
           countIf(verdict = 'SATISFIED') AS n_satisfied,
           countIf(verdict = 'NA') AS n_na,
           count() AS n_total,
           max(toUInt8(input_confidence)) AS worst_input
    FROM fresh GROUP BY cell_id_num
),
density AS (
    SELECT position_id, uniqExact(scene_id) AS active_scenes
    FROM fresh GROUP BY position_id
)
SELECT c.cell_id,
       c.priority_weight,
       toString(c.confidence) AS cell_confidence,
       coalesce(d.active_scenes, 0) AS scene_density,
       c.priority_weight * if(pc.worst_input = 2, 0.75, 1.0) AS severity,
       severity * (1 + log(1 + coalesce(d.active_scenes, 0))) AS urgency
FROM cells_src AS c
LEFT JOIN per_cell AS pc USING (cell_id_num)
LEFT JOIN density AS d ON c.position_id = d.position_id
WHERE pc.n_satisfied = 0
  AND NOT (pc.n_total > 0 AND pc.n_na = pc.n_total)
ORDER BY urgency DESC, c.cell_id ASC
LIMIT 15
"""

Q3 = """
WITH changed AS (
    SELECT arrayJoin(changed_slots) AS slot_id
    FROM bible_version_changes
    WHERE project_id = {project:UUID} AND bible_version_id = {version:UInt32}
),
affected_cells AS (
    SELECT DISTINCT csc.cell_id_num
    FROM cell_slot_consumption AS csc
    INNER JOIN changed AS ch USING (slot_id)
),
latest AS (
    SELECT scene_id, cell_id_num,
           argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
    FROM scene_diagnoses
    WHERE project_id = {project:UUID}
    GROUP BY scene_id, cell_id_num
)
SELECT l.scene_id, l.cell_id_num
FROM latest AS l
INNER JOIN affected_cells AS ac USING (cell_id_num)
WHERE l.bible_version_id < {version:UInt32}
ORDER BY l.scene_id
"""

Q4 = LATEST + """
SELECT toString(dictGetOrDefault('x','x',toUInt64(0),'')) AS unused
""" if False else LATEST + """
SELECT p.act AS act,
       ln.name AS lens,
       uniqExact(c.position_id) AS total_positions,
       uniqExactIf(c.position_id, f.verdict = 'SATISFIED') AS satisfied_positions,
       concat(toString(act), ' touches ', lens, ' in ',
              toString(satisfied_positions), ' of ',
              toString(total_positions), ' positions') AS sentence
FROM cells_src AS c
INNER JOIN positions_src AS p ON c.position_id = p.position_id
INNER JOIN lenses_src AS ln ON c.lens_id = ln.lens_id
LEFT JOIN fresh AS f USING (cell_id_num)
GROUP BY act, lens
ORDER BY act, lens
"""

Q5 = LATEST + """
SELECT count() AS stale_rows FROM latest WHERE bible_version_id < {version:UInt32}
"""

def run(name, sql, limit=None):
    print(f"\n{'='*70}\n{name}\n{'='*70}")
    try:
        r = client.query(sql, parameters=P)
        rows = r.result_rows[:limit] if limit else r.result_rows
        print("cols:", r.column_names)
        for row in rows:
            print(row)
        print(f"-- {len(r.result_rows)} rows")
    except Exception as e:
        print("FAIL:", e)

run("Q1 COVERAGE HEATMAP", Q1, limit=12)
run("Q2 RANKED GAPS", Q2)
run("Q3 NARROWED RE-DIAGNOSIS", Q3, limit=10)
run("Q4 STRUCTURAL SUMMARY", Q4)
run("Q5 STALENESS COUNT", Q5)
