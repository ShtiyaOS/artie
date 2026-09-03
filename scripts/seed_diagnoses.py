import os, uuid, time, random
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

PROJECT = uuid.UUID("4f27d81a-6d0e-4361-b1e1-e137c6888c3a")
CURRENT_VERSION = 5
random.seed(42)

# Scenes per position — deliberately skewed to mirror range widths
SCENES = {1:2, 2:1, 3:3, 4:1, 5:6, 6:1, 7:8, 8:2, 9:1, 10:1, 11:2, 12:1}

rows = []
now = int(time.time() * 1_000_000)

for position, count in SCENES.items():
    for _ in range(count):
        scene_id = uuid.uuid4()
        # one stale scene at X07 to exercise staleness
        version = 3 if (position == 7 and len(rows) % 17 == 0) else CURRENT_VERSION
        for lens in range(1, 7):
            cell_id_num = position * 10 + lens
            if position == 12 and lens == 5:
                verdict = "NA"
            elif random.random() < 0.62:
                verdict = "SATISFIED"
            else:
                verdict = "GAP"
            conf = "PROVISIONAL" if random.random() < 0.15 else "VALIDATED"
            rows.append([PROJECT, scene_id, position, cell_id_num,
                         version, verdict, conf, now])
            now += 1

client.command("TRUNCATE TABLE IF EXISTS scene_diagnoses")
client.insert("scene_diagnoses", rows, column_names=[
    "project_id","scene_id","position_id","cell_id_num",
    "bible_version_id","verdict","input_confidence","diagnosed_at_micros"])

print("Inserted", len(rows), "diagnoses across",
      len({r[1] for r in rows}), "scenes")

# Slot consumption: S06 feeds all Y4 cells
consumption = [[p*10+4, "S06"] for p in range(1, 13)]
consumption += [[p*10+2, "S05"] for p in range(1, 13)]
consumption += [[1*10+3, "S04"], [8*10+3, "S04"], [11*10+3, "S04"], [12*10+3, "S04"]]
client.command("TRUNCATE TABLE IF EXISTS cell_slot_consumption")
client.insert("cell_slot_consumption", consumption,
              column_names=["cell_id_num","slot_id"])
print("Inserted", len(consumption), "slot-consumption rows")

# A Bible change at version 5 touching S06
client.command("TRUNCATE TABLE IF EXISTS bible_version_changes")
client.insert("bible_version_changes",
    [[PROJECT, 5, ["S06"], int(time.time())]],
    column_names=["project_id","bible_version_id","changed_slots","committed_at"])
print("Inserted bible change: v5 changed S06")
