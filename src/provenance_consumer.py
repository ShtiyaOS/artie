"""
Confluent → ClickHouse provenance consumer.

Reads authorship.events, batch-inserts rows into provenance_events.

Batching: 500 events or 5 seconds, whichever comes first.
Offset commit: after a successful ClickHouse insert (at-least-once).
See docs/09_provenance_ledger.md §8 and §12.

Usage:
    python -m src.provenance_consumer

Environment variables required (same as confluent_producer.py + clickhouse_client.py):
    CONFLUENT_BOOTSTRAP_SERVERS, CONFLUENT_API_KEY, CONFLUENT_API_SECRET,
    CONFLUENT_TOPIC,
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD,
    CLICKHOUSE_SECURE (optional, default true)
"""

import json
import logging
import os
import signal
import time
import uuid

from dotenv import load_dotenv

load_dotenv()

from confluent_kafka import Consumer, KafkaError  # noqa: E402

from src.clickhouse_client import get_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_TIMEOUT_SECS = 5.0

# actor string → Enum8 integer (schema: docs/09_provenance_ledger.md §9)
ACTOR_MAP = {
    "human": 1,
    "artie": 2,
    "supervisor": 3,
    "director": 4,
    "system": 5,
}

_running = True


def _handle_signal(signum, _frame):
    global _running
    logger.info("Signal %d received — shutting down consumer", signum)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def _build_consumer() -> Consumer:
    conf = {
        "bootstrap.servers": os.environ["CONFLUENT_BOOTSTRAP_SERVERS"],
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": os.environ["CONFLUENT_API_KEY"],
        "sasl.password": os.environ["CONFLUENT_API_SECRET"],
        "group.id": "artie-provenance-consumer",
        "auto.offset.reset": "earliest",
        # Disable auto-commit; we commit after successful insert (§8, §12)
        "enable.auto.commit": False,
    }
    return Consumer(conf)


def _parse_row(msg_value: bytes) -> list | None:
    """
    Parse a Confluent message into a ClickHouse row tuple.
    Returns None if the message cannot be mapped to a valid row.

    Column order matches provenance_events INSERT below:
        event_id, event_type, project_id, scene_id, bible_version_id,
        actor, ts_micros, payload
    """
    try:
        envelope = json.loads(msg_value.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Skipping unparseable message")
        return None

    event_id_raw = envelope.get("event_id")
    try:
        event_id = uuid.UUID(str(event_id_raw))
    except (TypeError, ValueError):
        logger.warning("Skipping message with invalid event_id: %s", event_id_raw)
        return None

    project_id_raw = envelope.get("project_id")
    try:
        project_id = uuid.UUID(str(project_id_raw))
    except (TypeError, ValueError):
        logger.warning("Skipping message with invalid project_id: %s", project_id_raw)
        return None

    scene_id_raw = envelope.get("scene_id")
    scene_id: uuid.UUID | None = None
    if scene_id_raw:
        try:
            scene_id = uuid.UUID(str(scene_id_raw))
        except (TypeError, ValueError):
            scene_id = None

    actor_str = str(envelope.get("actor", "system"))
    actor_int = ACTOR_MAP.get(actor_str, ACTOR_MAP["system"])

    payload = envelope.get("payload", {})
    payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)

    return [
        event_id,
        str(envelope.get("event_type", "")),
        project_id,
        scene_id,
        int(envelope.get("bible_version_id", 0)),
        actor_int,
        int(envelope.get("ts_micros", 0)),
        payload_str,
    ]


def _flush_batch(batch: list[list], consumer: Consumer) -> None:
    """
    Insert batch into ClickHouse, then commit offsets.
    Raises on ClickHouse error so the caller does not commit.
    """
    ch = get_client()
    ch.insert(
        "provenance_events",
        batch,
        column_names=[
            "event_id",
            "event_type",
            "project_id",
            "scene_id",
            "bible_version_id",
            "actor",
            "ts_micros",
            "payload",
        ],
    )
    logger.info("Inserted %d events into provenance_events", len(batch))
    consumer.commit(asynchronous=False)
    logger.info("Offsets committed")


def run() -> None:
    topic = os.environ["CONFLUENT_TOPIC"]
    consumer = _build_consumer()
    consumer.subscribe([topic])
    logger.info("Subscribed to %s", topic)

    batch: list[list] = []
    batch_deadline = time.monotonic() + BATCH_TIMEOUT_SECS

    try:
        while _running:
            now = time.monotonic()
            remaining = batch_deadline - now
            # Never block longer than the batch timeout
            timeout = max(0.1, min(remaining, 1.0))
            msg = consumer.poll(timeout)

            if msg is None:
                pass  # poll timeout — fall through to flush check
            elif msg.error():
                err = msg.error()
                if err.code() == KafkaError._PARTITION_EOF:
                    pass  # normal end-of-partition, not an error
                else:
                    logger.error("Consumer error: %s", err)
            else:
                row = _parse_row(msg.value())
                if row is not None:
                    batch.append(row)

            # Flush on size or timeout
            flush_due = time.monotonic() >= batch_deadline
            if batch and (len(batch) >= BATCH_SIZE or flush_due):
                try:
                    _flush_batch(batch, consumer)
                except Exception:
                    logger.exception("ClickHouse insert failed; not committing offsets")
                batch = []
                batch_deadline = time.monotonic() + BATCH_TIMEOUT_SECS
            elif flush_due:
                # Reset deadline even when batch is empty
                batch_deadline = time.monotonic() + BATCH_TIMEOUT_SECS

    finally:
        # Flush any remaining events before shutdown
        if batch:
            try:
                _flush_batch(batch, consumer)
            except Exception:
                logger.exception("Final flush failed")
        consumer.close()
        logger.info("Consumer closed")


if __name__ == "__main__":
    run()
