import os, json, time, uuid
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer

load_dotenv()

conf = {
    "bootstrap.servers": os.environ["CONFLUENT_BOOTSTRAP_SERVERS"],
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.environ["CONFLUENT_API_KEY"],
    "sasl.password": os.environ["CONFLUENT_API_SECRET"],
}
topic = os.environ["CONFLUENT_TOPIC"]

event = {
    "event_id": str(uuid.uuid4()),
    "event_type": "SCENE_SAVED",
    "actor": "human",
    "scene_id": str(uuid.uuid4()),
    "ts_micros": int(time.time() * 1_000_000),
}

def ack(err, msg):
    if err:
        print("Delivery failed:", err)
    else:
        print(f"Produced to {msg.topic()} partition {msg.partition()} offset {msg.offset()}")

p = Producer(conf)
p.produce(topic, json.dumps(event).encode("utf-8"), callback=ack)
p.flush(10)

c = Consumer({**conf,
              "group.id": "artie-smoke-test",
              "auto.offset.reset": "earliest"})
c.subscribe([topic])

print("Consuming...")
deadline = time.time() + 20
while time.time() < deadline:
    msg = c.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print("Consumer error:", msg.error())
        continue
    print("Consumed:", json.loads(msg.value().decode("utf-8")))
    break
else:
    print("Timed out — no message received")

c.close()
