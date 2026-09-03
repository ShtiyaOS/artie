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

# Extrapolated cells per Locked Axis Spec v1.1 §5
EXTRAPOLATED = set()
for p in range(1, 13):
    if p != 11:
        EXTRAPOLATED.add((p, 4))          # Y4 outside X11
for p in (3, 5, 6, 9):
    EXTRAPOLATED.add((p, 6))              # Y6 connective + midpoint
EXTRAPOLATED.add((9, 5))                  # X09.Y5

# Anchored: the eleven Y4 cells (conditional on S06)
ANCHORED = {(p, 4) for p in range(1, 13) if p != 11}

# Weight-5 cells, all ATTESTED, at turning points
WEIGHT_5 = {(2,1),(4,3),(6,1),(6,2),(8,2),(8,3),(11,1),(11,3)}

# TRANSFORMATION cells: all X12 plus X11.Y3, compared to X01
TRANSFORMATION = {(12, l) for l in range(1, 7)} | {(11, 3)}

rows = []
for p in range(1, 13):
    for l in range(1, 7):
        key = (p, l)
        cell_id_num = p * 10 + l
        cell_id = f"X{p:02d}.Y{l}"
        mode = "TRANSFORMATION" if key in TRANSFORMATION else "ACTIVATION"
        compare_to = 1 if key in TRANSFORMATION else None
        na_cond = "X12 contains no protagonist dialogue" if key == (12, 5) else None

        if key in ANCHORED:
            conf, cap = "ANCHORED", 4
        elif key in EXTRAPOLATED:
            conf, cap = "EXTRAPOLATED", 3
        else:
            conf, cap = "ATTESTED", 5

        weight = 5 if key in WEIGHT_5 else 3
        weight = min(weight, cap)

        rows.append([cell_id_num, cell_id, p, l, mode,
                     compare_to, na_cond, conf, weight])

client.command("TRUNCATE TABLE IF EXISTS cells_src")
client.insert("cells_src", rows, column_names=[
    "cell_id_num","cell_id","position_id","lens_id","cell_mode",
    "compare_to_position","not_applicable_condition","confidence","priority_weight"
])

print("Inserted", len(rows), "cells")
for r in client.query(
    "SELECT confidence, count(), max(priority_weight) "
    "FROM cells_src GROUP BY confidence ORDER BY confidence"
).result_rows:
    print(r)
