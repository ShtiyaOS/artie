import os, re
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=8443,
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=True,
)

raw = open("sql/03_seed_cell_slot_consumption.sql").read()
rows = [[int(a), b] for a, b in re.findall(r"\((\d+),\s*'(\w+)'\)", raw)]
print("parsed:", len(rows))

client.command("TRUNCATE TABLE cell_slot_consumption")
client.insert("cell_slot_consumption", rows, column_names=["cell_id_num", "slot_id"])

print(client.query(
    "SELECT slot_id, count() FROM cell_slot_consumption GROUP BY slot_id ORDER BY slot_id"
).result_rows)
