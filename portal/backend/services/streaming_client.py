"""Streaming & Messaging integrations: Redpanda (Kafka-compatible) & RabbitMQ Management API."""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer, TopicPartition
from kafka.admin import NewTopic

from core.config import settings

logger = logging.getLogger("ues.streaming")


def get_kafka_overview() -> Dict[str, Any]:
    """Query Redpanda / Kafka topics, partitions, consumer groups, and real consumer lag."""
    try:
        admin = KafkaAdminClient(bootstrap_servers=[settings.KAFKA_BROKER], request_timeout_ms=2500)
        consumer = KafkaConsumer(bootstrap_servers=[settings.KAFKA_BROKER], request_timeout_ms=2500)
        try:
            topic_names = sorted([t for t in consumer.topics() if not t.startswith("__")])
            topics_detail = []
            for t in topic_names:
                parts = consumer.partitions_for_topic(t) or set()
                tps = [TopicPartition(t, p) for p in parts]
                end_offsets = consumer.end_offsets(tps) if tps else {}
                beg_offsets = consumer.beginning_offsets(tps) if tps else {}
                total_msgs = sum(max(0, end_offsets.get(tp, 0) - beg_offsets.get(tp, 0)) for tp in tps)
                topics_detail.append(
                    {
                        "name": t,
                        "partitions": len(parts),
                        "estimated_messages": total_msgs,
                    }
                )

            groups_out = []
            total_lag = 0
            try:
                groups = admin.list_consumer_groups()
                for g_id, _proto in groups:
                    if g_id.startswith("__"):
                        continue
                    g_lag = 0
                    part_lags = []
                    try:
                        offsets = admin.list_consumer_group_offsets(g_id)
                        end_off = consumer.end_offsets(list(offsets.keys())) if offsets else {}
                        for tp, meta in offsets.items():
                            high = end_off.get(tp, 0)
                            committed = max(0, meta.offset) if meta and meta.offset >= 0 else 0
                            lag = max(0, high - committed)
                            g_lag += lag
                            part_lags.append({"topic": tp.topic, "partition": tp.partition, "committed": committed, "high_watermark": high, "lag": lag})
                    except Exception:
                        pass
                    total_lag += g_lag
                    groups_out.append({"group_id": g_id, "total_lag": g_lag, "partitions": part_lags})
            except Exception:
                pass

            return {
                "available": True,
                "broker": settings.KAFKA_BROKER,
                "topic_count": len(topics_detail),
                "topics": topics_detail,
                "consumer_groups": groups_out,
                "total_consumer_lag": total_lag,
            }
        finally:
            consumer.close()
            admin.close()
    except Exception as exc:
        return {
            "available": False,
            "broker": settings.KAFKA_BROKER,
            "error": str(exc),
            "topic_count": 0,
            "topics": [],
            "consumer_groups": [],
            "total_consumer_lag": 0,
        }


def create_kafka_topic(topic_name: str, partitions: int = 1) -> Dict[str, Any]:
    admin = KafkaAdminClient(bootstrap_servers=[settings.KAFKA_BROKER], request_timeout_ms=3000)
    try:
        admin.create_topics([NewTopic(name=topic_name, num_partitions=max(1, min(partitions, 6)), replication_factor=1)])
        return {"topic": topic_name, "partitions": partitions, "status": "created"}
    finally:
        admin.close()


def produce_kafka_message(topic_name: str, message: str, key: Optional[str] = None) -> Dict[str, Any]:
    producer = KafkaProducer(bootstrap_servers=[settings.KAFKA_BROKER], request_timeout_ms=3000)
    try:
        fut = producer.send(
            topic_name,
            key=key.encode("utf-8") if key else None,
            value=message.encode("utf-8"),
        )
        meta = fut.get(timeout=4)
        producer.flush()
        return {"topic": topic_name, "partition": meta.partition, "offset": meta.offset, "status": "sent"}
    finally:
        producer.close()


async def get_rabbitmq_overview() -> Dict[str, Any]:
    """Query RabbitMQ Management HTTP API for overview, exchanges, queues, DLQs, and rates."""
    base = settings.RABBITMQ_MGMT_URL.rstrip("/")
    auth = (settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=auth) as client:
            ov_r = await client.get(f"{base}/api/overview")
            q_r = await client.get(f"{base}/api/queues")
            ex_r = await client.get(f"{base}/api/exchanges")
            if ov_r.status_code != 200:
                return {"available": False, "error": f"RabbitMQ API HTTP {ov_r.status_code}", "queues": [], "exchanges": []}

            ov = ov_r.json()
            queues_raw = q_r.json() if q_r.status_code == 200 else []
            ex_raw = ex_r.json() if ex_r.status_code == 200 else []

            queues = []
            dlqs = []
            total_messages = 0
            for q in queues_raw:
                msgs = int(q.get("messages", 0))
                total_messages += msgs
                q_item = {
                    "name": q.get("name"),
                    "vhost": q.get("vhost", "/"),
                    "state": q.get("state", "running"),
                    "messages": msgs,
                    "messages_ready": int(q.get("messages_ready", 0)),
                    "messages_unacknowledged": int(q.get("messages_unacknowledged", 0)),
                    "consumers": int(q.get("consumers", 0)),
                    "publish_rate": (q.get("message_stats", {}) or {}).get("publish_details", {}).get("rate", 0.0),
                    "deliver_rate": (q.get("message_stats", {}) or {}).get("deliver_get_details", {}).get("rate", 0.0),
                    "is_dlq": "dlq" in q.get("name", "").lower() or "dead" in q.get("name", "").lower(),
                }
                queues.append(q_item)
                if q_item["is_dlq"]:
                    dlqs.append(q_item)

            exchanges = [
                {
                    "name": e.get("name") or "(AMQP default)",
                    "type": e.get("type"),
                    "durable": e.get("durable"),
                    "vhost": e.get("vhost"),
                }
                for e in ex_raw
                if not str(e.get("name", "")).startswith("amq.")
            ]

            msg_stats = ov.get("message_stats", {}) or {}
            return {
                "available": True,
                "rabbitmq_version": ov.get("rabbitmq_version", ""),
                "queue_totals": ov.get("queue_totals", {}),
                "total_messages": total_messages,
                "publish_rate": (msg_stats.get("publish_details") or {}).get("rate", 0.0),
                "deliver_rate": (msg_stats.get("deliver_get_details") or {}).get("rate", 0.0),
                "queues": queues,
                "dlqs": dlqs,
                "exchanges": exchanges,
            }
    except Exception as exc:
        return {"available": False, "error": str(exc), "queues": [], "dlqs": [], "exchanges": [], "total_messages": 0}


async def rabbitmq_publish_test_message(queue_name: str, payload: str) -> Dict[str, Any]:
    base = settings.RABBITMQ_MGMT_URL.rstrip("/")
    auth = (settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    async with httpx.AsyncClient(timeout=4.0, auth=auth) as client:
        # Ensure queue exists
        await client.put(f"{base}/api/queues/%2F/{queue_name}", json={"durable": True})
        res = await client.post(
            f"{base}/api/exchanges/%2F/amq.default/publish",
            json={
                "properties": {"delivery_mode": 2},
                "routing_key": queue_name,
                "payload": payload,
                "payload_encoding": "string",
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"RabbitMQ publish failed ({res.status_code})")
        return {"queue": queue_name, "routed": res.json().get("routed", False)}


async def rabbitmq_purge_queue(queue_name: str) -> Dict[str, Any]:
    base = settings.RABBITMQ_MGMT_URL.rstrip("/")
    auth = (settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    async with httpx.AsyncClient(timeout=4.0, auth=auth) as client:
        res = await client.delete(f"{base}/api/queues/%2F/{queue_name}/contents")
        if res.status_code not in (200, 204):
            raise RuntimeError(f"RabbitMQ purge failed ({res.status_code})")
        return {"queue": queue_name, "status": "purged"}

