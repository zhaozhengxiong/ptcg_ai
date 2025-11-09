"""Atomic operations available to the referee agent."""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence

from .database import DatabaseClient
from .models import CardInstance, GameLogEntry, GameState, Zone


def _make_seed() -> str:
    return secrets.token_hex(16)


@dataclass
class ToolCallContext:
    """Context object injected into every tool call."""

    match_id: str
    referee_id: str
    db: DatabaseClient


@dataclass
class GameTools:
    """Collection of stateful atomic operations.

    The tools never perform rule validation. They simply manipulate the game
    state as instructed by the referee agent while generating detailed logs.
    """

    context: ToolCallContext
    state: GameState
    _rng: Callable[[], str] = field(default=_make_seed, repr=False)

    # ------------------------------------------------------------------
    # deck and card queries
    # ------------------------------------------------------------------
    def deck_query(self, player_id: str, predicate: Callable[[CardInstance], bool]) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        return [card for card in deck.cards if predicate(card)]

    def reveal_top(self, player_id: str, count: int) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        self._record_zone(player_id, Zone.DECK)
        return deck.cards[:count]

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------
    def select_from_candidates(self, candidates: Sequence[CardInstance], max_n: int) -> List[CardInstance]:
        return list(candidates[:max_n])

    # ------------------------------------------------------------------
    # card movement
    # ------------------------------------------------------------------
    def move_card(self, player_id: str, source: Zone, target: Zone, card: CardInstance, position_hint: Optional[int] = None) -> None:
        source_zone = self.state.players[player_id].zone(source)
        target_zone = self.state.players[player_id].zone(target)
        if card not in source_zone.cards:
            raise ValueError(f"Card {card.uid} not found in {source.value}")
        source_zone.cards.remove(card)
        if position_hint is None or position_hint >= len(target_zone.cards):
            target_zone.cards.append(card)
        else:
            target_zone.cards.insert(position_hint, card)
        self._log(
            actor=self.context.referee_id,
            action="move_card",
            payload={
                "card": card.uid,
                "source": source.value,
                "target": target.value,
                "position_hint": position_hint,
            },
        )

    def shuffle(self, player_id: str, zone: Zone) -> None:
        zone_state = self.state.players[player_id].zone(zone)
        seed = self._rng()
        rng = random.Random(int(seed, 16))
        rng.shuffle(zone_state.cards)  # type: ignore[arg-type]
        self._log(
            actor=self.context.referee_id,
            action="shuffle",
            payload={"player_id": player_id, "zone": zone.value},
            random_seed=seed,
        )

    def draw(self, player_id: str, count: int) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        hand = self.state.players[player_id].zone(Zone.HAND)
        drawn = deck.cards[:count]
        del deck.cards[:count]
        hand.cards.extend(drawn)
        self._log(
            actor=self.context.referee_id,
            action="draw",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in drawn]},
        )
        return drawn

    def discard(self, player_id: str, cards: Iterable[CardInstance], reason: str) -> None:
        discard_pile = self.state.players[player_id].zone(Zone.DISCARD)
        hand = self.state.players[player_id].zone(Zone.HAND)
        for card in cards:
            if card in hand.cards:
                hand.cards.remove(card)
            discard_pile.cards.append(card)
        self._log(
            actor=self.context.referee_id,
            action="discard",
            payload={
                "player_id": player_id,
                "reason": reason,
                "cards": [card.uid for card in cards],
            },
        )

    def take_prize(self, player_id: str, count: int = 1) -> List[CardInstance]:
        prize_zone = self.state.players[player_id].zone(Zone.PRIZE)
        hand = self.state.players[player_id].zone(Zone.HAND)
        taken = prize_zone.cards[:count]
        del prize_zone.cards[:count]
        hand.cards.extend(taken)
        self.state.players[player_id].prizes_remaining -= len(taken)
        self._log(
            actor=self.context.referee_id,
            action="take_prize",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in taken]},
        )
        return taken

    def random_discard(self, player_id: str, count: int) -> List[CardInstance]:
        hand = self.state.players[player_id].zone(Zone.HAND)
        if count > len(hand.cards):
            raise ValueError("Cannot discard more cards than available in hand")
        seed = self._rng()
        rng = random.Random(int(seed, 16))
        selected = rng.sample(hand.cards, count)
        for card in selected:
            hand.cards.remove(card)
            self.state.players[player_id].zone(Zone.DISCARD).cards.append(card)
        self._log(
            actor=self.context.referee_id,
            action="random_discard",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in selected]},
            random_seed=seed,
        )
        return selected

    # ------------------------------------------------------------------
    # logging helpers
    # ------------------------------------------------------------------
    def _record_zone(self, player_id: str, zone: Zone) -> None:
        state = self.state.players[player_id].zone(zone)
        self.context.db.record_zone(self.state.match_id, player_id, zone, state.cards)

    def _log(self, actor: str, action: str, payload: dict, random_seed: Optional[str] = None) -> None:
        entry = GameLogEntry(
            match_id=self.state.match_id,
            actor=actor,
            action=action,
            payload=payload,
            random_seed=random_seed,
        )
        self.context.db.append_log(entry)


__all__ = ["GameTools", "ToolCallContext"]
