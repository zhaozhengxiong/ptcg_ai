"""Core datamodels for the PTCG AI battle system."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class Zone(str, Enum):
    """Enumeration of card zones recognised by the engine."""

    DECK = "deck"
    HAND = "hand"
    ACTIVE = "active"
    BENCH = "bench"
    DISCARD = "discard"
    LOST_ZONE = "lost_zone"
    PRIZE = "prize"
    STADIUM = "stadium"


@dataclass(slots=True)
class CardDefinition:
    """Static card information shared by all instances."""

    set_code: str
    number: str
    name: str
    card_type: str
    hp: Optional[int] = None
    stage: Optional[str] = None
    rules_text: Optional[str] = None
    subtypes: Optional[List[str]] = None
    abilities: Optional[List[Dict[str, object]]] = None
    attacks: Optional[List[Dict[str, object]]] = None


@dataclass(slots=True)
class CardInstance:
    """Runtime representation of a specific physical card."""

    uid: str
    owner_id: str
    definition: CardDefinition
    damage: int = 0  # Current damage on this card (for Pokémon)
    attached_energy: List[str] = field(default_factory=list)  # List of energy card UIDs attached to this card
    special_conditions: List[str] = field(default_factory=list)  # Special conditions (Asleep, Burned, Confused, Paralyzed, Poisoned)

    def __hash__(self) -> int:  # pragma: no cover - delegated to uid
        return hash(self.uid)
    
    @property
    def hp(self) -> Optional[int]:
        """Get HP value from definition."""
        return self.definition.hp
    
    @property
    def is_ko(self) -> bool:
        """Check if this Pokémon is knocked out (damage >= HP)."""
        if self.hp is None:
            return False
        return self.damage >= self.hp


@dataclass
class ZoneState:
    """Zone contents and metadata."""

    cards: List[CardInstance] = field(default_factory=list)

    def copy(self) -> "ZoneState":
        return ZoneState(cards=list(self.cards))


@dataclass
class Deck:
    """Full deck for a player."""

    player_id: str
    cards: Sequence[CardInstance]

    def validate(self) -> None:
        """Ensure the deck is legal according to baseline constraints."""

        if len(self.cards) != 60:
            raise ValueError(
                f"Deck for {self.player_id} must contain exactly 60 cards, "
                f"received {len(self.cards)}"
            )
        uids = {card.uid for card in self.cards}
        if len(uids) != 60:
            raise ValueError("Every card in the deck must have a unique uid")


@dataclass
class PlayerState:
    """Mutable view of a player's zones."""

    player_id: str
    zones: Dict[Zone, ZoneState] = field(default_factory=lambda: {zone: ZoneState() for zone in Zone})
    prizes_remaining: int = 6
    memory: List[str] = field(default_factory=list)
    usage_trackers: Dict[str, Dict[str, int]] = field(default_factory=dict)  # Track usage: {entity_id: {counter_type: count}}

    def zone(self, zone: Zone) -> ZoneState:
        return self.zones.setdefault(zone, ZoneState())
    
    def track_usage(self, entity_id: str, counter_type: str, scope: str = "turn") -> None:
        """Track usage of an ability/attack. Scope can be 'turn' or 'game'."""
        if entity_id not in self.usage_trackers:
            self.usage_trackers[entity_id] = {}
        key = f"{scope}:{counter_type}"
        self.usage_trackers[entity_id][key] = self.usage_trackers[entity_id].get(key, 0) + 1
    
    def get_usage_count(self, entity_id: str, counter_type: str, scope: str = "turn") -> int:
        """Get usage count for an ability/attack."""
        if entity_id not in self.usage_trackers:
            return 0
        key = f"{scope}:{counter_type}"
        return self.usage_trackers[entity_id].get(key, 0)
    
    def reset_turn_usage(self) -> None:
        """Reset all turn-scoped usage trackers (called at end of turn)."""
        for entity_id in list(self.usage_trackers.keys()):
            turn_keys = [k for k in self.usage_trackers[entity_id].keys() if k.startswith("turn:")]
            for key in turn_keys:
                del self.usage_trackers[entity_id][key]
            if not self.usage_trackers[entity_id]:
                del self.usage_trackers[entity_id]


@dataclass
class GameState:
    """Composite state tracked by the referee."""

    match_id: str
    players: Dict[str, PlayerState]
    turn_player: Optional[str] = None
    turn_number: int = 0
    phase: str = "init"

    def snapshot(self) -> Dict[str, Dict[str, List[str]]]:
        """Produce a serialisable snapshot for audit and tooling."""

        return {
            player_id: {
                zone.value: [card.uid for card in state.zone(zone).cards]
                for zone in Zone
            }
            for player_id, state in self.players.items()
        }


@dataclass(slots=True)
class GameLogEntry:
    """Structured log entry recorded for every atomic operation."""

    match_id: str
    actor: str
    action: str
    payload: Dict[str, object]
    random_seed: Optional[str] = None


__all__ = [
    "CardDefinition",
    "CardInstance",
    "Deck",
    "PlayerState",
    "GameState",
    "Zone",
    "ZoneState",
    "GameLogEntry",
]
