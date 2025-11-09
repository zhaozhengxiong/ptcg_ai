"""Base implementation for AI player agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .referee import OperationRequest


@dataclass
class PlayerMemory:
    """Simple rolling memory used by player agents."""

    thoughts: List[str] = field(default_factory=list)
    max_entries: int = 20

    def remember(self, entry: str) -> None:
        self.thoughts.append(entry)
        if len(self.thoughts) > self.max_entries:
            del self.thoughts[0]


@dataclass
class PlayerAgent:
    """Base class for player agents.

    Concrete strategies should override :meth:`decide` to analyse the game
    snapshot provided by the referee and emit an :class:`OperationRequest`.
    """

    player_id: str
    memory: PlayerMemory = field(default_factory=PlayerMemory)

    def decide(self, observation: Dict[str, object]) -> Optional[OperationRequest]:
        """Return the next action to perform.

        The base implementation is intentionally simple: it analyses the number
        of cards in hand and attempts to draw if the hand is empty. Sub-classes
        can implement more advanced logic or incorporate machine learning
        policies.
        """

        hand_cards = observation.get("hand_size", 0)
        if isinstance(hand_cards, int) and hand_cards == 0:
            self.memory.remember("Requested draw due to empty hand")
            return OperationRequest(actor_id=self.player_id, action="draw", payload={"count": 1})
        return None


__all__ = ["PlayerAgent", "PlayerMemory"]
