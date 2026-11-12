"""Streaming & Messaging Router (`/api/v1/streaming`)."""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, security
from services import streaming_client

router = APIRouter(prefix="/api/v1/streaming", tags=["Streaming & Messaging"])


class KafkaTopicCreateRequest(BaseModel):
    topic: str
    partitions: int = 1


class KafkaProduceRequest(BaseModel):
    topic: str
    message: str
    key: Optional[str] = None


class RabbitPublishRequest(BaseModel):
    queue: str
    payload: str


@router.get("/overview")
async def streaming_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    kafka = streaming_client.get_kafka_overview()
    rabbitmq = await streaming_client.get_rabbitmq_overview()
    return {"kafka": kafka, "rabbitmq": rabbitmq}


@router.post("/kafka/topics")
def create_kafka_topic(req: KafkaTopicCreateRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = streaming_client.create_kafka_topic(req.topic, req.partitions)
        audit.record_audit(admin, "kafka.create_topic", req.topic, f"partitions={req.partitions}")
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/kafka/produce")
def produce_kafka(req: KafkaProduceRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = streaming_client.produce_kafka_message(req.topic, req.message, key=req.key)
        audit.record_audit(admin, "kafka.produce", req.topic, f"offset={res['offset']}")
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/rabbitmq/publish")
async def publish_rabbitmq(req: RabbitPublishRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = await streaming_client.rabbitmq_publish_test_message(req.queue, req.payload)
        audit.record_audit(admin, "rabbitmq.publish", req.queue, "Published test message")
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/rabbitmq/queues/{queue_name}/purge")
async def purge_rabbitmq_queue(queue_name: str, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = await streaming_client.rabbitmq_purge_queue(queue_name)
        audit.record_audit(admin, "rabbitmq.purge", queue_name, "Purged queue")
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

