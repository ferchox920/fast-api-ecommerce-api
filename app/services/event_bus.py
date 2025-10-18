from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class EventRecord:
    name: str
    payload: Dict[str, Any]


_PROMOTION_EVENTS: List[EventRecord] = []
_LOYALTY_EVENTS: List[EventRecord] = []


def emit_promotion_event(name: str, payload: Dict[str, Any]) -> None:
    """Queue promotion events to be consumed by adapters.

    # INTEGRATION: Notificaciones (email/WS) escucharán 'promotion_start'.
    # TODO: reemplazar por broker real (Kafka/Rabbit) con compaction.
    """
    _PROMOTION_EVENTS.append(EventRecord(name=name, payload=payload))


def emit_loyalty_event(name: str, payload: Dict[str, Any]) -> None:
    """Queue loyalty events to be consumed by adapters."""
    _LOYALTY_EVENTS.append(EventRecord(name=name, payload=payload))


def get_promotion_events() -> List[EventRecord]:
    return list(_PROMOTION_EVENTS)


def get_loyalty_events() -> List[EventRecord]:
    return list(_LOYALTY_EVENTS)
