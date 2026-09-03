import os, sys
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

path = sys.argv[1]
sql = open(path).read()

statements = [s.strip() for s in sql.split(";") if s.strip()]

for i, stmt in enumerate(statements, 1):
    head = stmt.splitlines()[0][:70]
    try:
        client.command(stmt)
        print(f"[{i}] OK   {head}")
    except Exception as e:
        print(f"[{i}] FAIL {head}")
        print(f"     {e}")
