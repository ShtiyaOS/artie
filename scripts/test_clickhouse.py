import os
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=int(os.environ["CLICKHOUSE_PORT"]),
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
)

print("Connected.")
print("Version:", client.query("SELECT version()").result_rows[0][0])
print("Database:", client.query("SELECT currentDatabase()").result_rows[0][0])
