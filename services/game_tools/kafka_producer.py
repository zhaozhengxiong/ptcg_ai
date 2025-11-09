"""Kafka producer for Game Tools events."""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

logger = logging.getLogger(__name__)


class GameToolsKafkaProducer:
    """Kafka producer for game events."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "ptcg-game-events",
        enabled: bool = True,
    ):
        """Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Topic name for events
            enabled: Whether to actually send events (for testing)
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.enabled = enabled and KafkaProducer is not None
        
        if self.enabled:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
                logger.info(f"Kafka 生产者已初始化，主题: {topic}")
            except Exception as e:
                logger.error(f"初始化 Kafka 生产者失败: {e}", exc_info=True)
                self.enabled = False
        else:
            self.producer = None
            if not enabled:
                logger.info("Kafka 生产者已禁用")
            else:
                logger.warning("Kafka 不可用，事件将不会被发布")

    def publish_event(
        self,
        match_id: str,
        event_type: str,
        actor: str,
        action: str,
        payload: Dict,
        random_seed: Optional[str] = None,
    ):
        """Publish a game event to Kafka.
        
        Args:
            match_id: Match identifier
            event_type: Type of event
            actor: Actor performing the action
            action: Action name
            payload: Event payload
            random_seed: Optional random seed
        """
        if not self.enabled:
            return

        event = {
            "match_id": match_id,
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "payload": payload,
            "random_seed": random_seed,
            "timestamp": None,  # Would be set by Kafka
        }

        try:
            self.producer.send(self.topic, value=event)
            self.producer.flush()
        except Exception as e:
            logger.error(f"发布事件到 Kafka 时出错: {e}", exc_info=True)

    def close(self):
        """Close the producer."""
        if self.producer:
            self.producer.close()

