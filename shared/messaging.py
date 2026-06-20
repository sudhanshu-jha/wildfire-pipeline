"""
Transport abstraction for the wildfire pipeline.

Two implementations share the same interface (MessageBus):

  JetStreamBus  — NATS JetStream (default, single binary, no extra infra)
  KafkaBus      — Apache Kafka via aiokafka (set TRANSPORT=kafka)

Select via environment:
  TRANSPORT=nats   (default)
  TRANSPORT=kafka  + KAFKA_BOOTSTRAP_SERVERS=broker:9092

Service code only imports `create_bus()` and speaks to the MessageBus
interface, so swapping transports is a one-env-var change.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from pydantic import BaseModel

from shared.config import settings

logger = logging.getLogger(__name__)

MessageHandler = Callable[[bytes], Awaitable[None]]


# ── Abstract interface ────────────────────────────────────────────────────────

class MessageBus(ABC):
    @abstractmethod
    async def connect(self) -> "MessageBus": ...

    @abstractmethod
    async def ensure_stream(self, name: str, subjects: list[str]) -> None:
        """No-op on Kafka (topics are created on first publish)."""

    @abstractmethod
    async def publish(self, subject: str, event: BaseModel) -> None: ...

    @abstractmethod
    async def consume_loop(self, subject: str, durable: str, handler: MessageHandler) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


# ── NATS JetStream ────────────────────────────────────────────────────────────

class JetStreamBus(MessageBus):
    def __init__(self, nats_url: str):
        self.nats_url = nats_url
        self._nc = None
        self._js = None

    async def connect(self) -> "JetStreamBus":
        import nats as nats_lib
        self._nc = await nats_lib.connect(self.nats_url)
        self._js = self._nc.jetstream()
        logger.info("Connected to NATS at %s", self.nats_url)
        return self

    async def ensure_stream(self, name: str, subjects: list[str]) -> None:
        from nats.js.api import StreamConfig
        try:
            await self._js.add_stream(StreamConfig(name=name, subjects=subjects))
            logger.info("Created stream %s for subjects %s", name, subjects)
        except Exception as exc:
            logger.debug("Stream %s already present: %s", name, exc)

    async def publish(self, subject: str, event: BaseModel) -> None:
        payload = event.model_dump_json().encode()
        await self._js.publish(subject, payload)
        logger.info("-> %s  %s", subject, event.__class__.__name__)

    async def consume_loop(self, subject: str, durable: str, handler: MessageHandler) -> None:
        sub = await self._js.pull_subscribe(subject, durable=durable)
        logger.info("Listening on %s (durable=%s)", subject, durable)
        while True:
            try:
                msgs = await sub.fetch(10, timeout=5)
            except Exception:
                continue
            for msg in msgs:
                try:
                    await handler(msg.data)
                    await msg.ack()
                except Exception:
                    logger.exception("Handler failed on %s", subject)
                    await msg.nak()

    async def close(self) -> None:
        if self._nc:
            await self._nc.close()


# ── Kafka ─────────────────────────────────────────────────────────────────────

class KafkaBus(MessageBus):
    """
    Kafka transport via aiokafka.

    Subject names map directly to Kafka topic names.
    `ensure_stream` is a no-op — Kafka auto-creates topics on first publish
    (enable `auto.create.topics.enable=true` on the broker, which is the default).
    `durable` maps to the Kafka consumer group id.
    """

    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
        self._consumers: list = []

    async def connect(self) -> "KafkaBus":
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            raise RuntimeError(
                "aiokafka not installed. Add aiokafka to requirements.txt and rebuild."
            )
        self._producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self._producer.start()
        logger.info("Connected to Kafka at %s", self.bootstrap_servers)
        return self

    async def ensure_stream(self, name: str, subjects: list[str]) -> None:
        pass  # Kafka auto-creates topics on first publish

    async def publish(self, subject: str, event: BaseModel) -> None:
        payload = event.model_dump_json().encode()
        await self._producer.send_and_wait(subject, payload)
        logger.info("-> %s  %s", subject, event.__class__.__name__)

    async def consume_loop(self, subject: str, durable: str, handler: MessageHandler) -> None:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            subject,
            bootstrap_servers=self.bootstrap_servers,
            group_id=durable,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._consumers.append(consumer)
        await consumer.start()
        logger.info("Listening on Kafka topic %s (group=%s)", subject, durable)
        try:
            async for msg in consumer:
                try:
                    await handler(msg.value)
                    await consumer.commit()
                except Exception:
                    logger.exception("Handler failed on topic %s", subject)
        finally:
            await consumer.stop()

    async def close(self) -> None:
        for c in self._consumers:
            await c.stop()
        if self._producer:
            await self._producer.stop()


# ── Factory ───────────────────────────────────────────────────────────────────

def create_bus() -> MessageBus:
    """Return the transport configured by TRANSPORT env var (default: nats)."""
    transport = settings.transport.lower()
    if transport == "kafka":
        servers = settings.kafka_bootstrap_servers
        logger.info("Using Kafka transport (%s)", servers)
        return KafkaBus(servers)
    logger.info("Using NATS JetStream transport")
    return JetStreamBus(settings.nats_url)
