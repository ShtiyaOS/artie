"""
Confluent Kafka producer for the provenance ledger.

Topic: authorship.events (docs/09_provenance_ledger.md §7)
Event envelope: docs/09_provenance_ledger.md §2

Connection config mirrors scripts/test_confluent.py exactly.
"""

import json
import logging
import os
import time
import uuid

from confluent_kafka import Producer

logger = logging.getLogger(__name__)

_producer: Producer | None = None


def _get_producer() -> Producer:
    """Return the singleton Producer, creating it on first call."""
    global _producer
    if _producer is None:
        conf = {
            "bootstrap.servers": os.environ["CONFLUENT_BOOTSTRAP_SERVERS"],
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": os.environ["CONFLUENT_API_KEY"],
            "sasl.password": os.environ["CONFLUENT_API_SECRET"],
        }
        _producer = Producer(conf)
    return _producer


def _ack(err, msg):
    if err:
        logger.error("Confluent delivery failed: %s", err)
    else:
        logger.info(
            "Confluent: produced to %s partition %d offset %d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def publish_event(
    event_type: str,
    actor: str,
    payload: dict,
    *,
    project_id: str | None = None,
    scene_id: str | None = None,
    bible_version_id: int = 0,
) -> None:
    """
    Publish one event envelope to authorship.events.

    Partition key: scene_id if present, else project_id (§7).
    """
    topic = os.environ["CONFLUENT_TOPIC"]
    envelope = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "project_id": project_id,
        "scene_id": scene_id,
        "bible_version_id": bible_version_id,
        "actor": actor,
        "ts_micros": int(time.time() * 1_000_000),
        "payload": payload,
    }
    key = (scene_id or project_id or "").encode("utf-8") or None
    producer = _get_producer()
    producer.produce(
        topic,
        value=json.dumps(envelope).encode("utf-8"),
        key=key,
        callback=_ack,
    )
    # poll(0) serves delivery callbacks without blocking
    producer.poll(0)
