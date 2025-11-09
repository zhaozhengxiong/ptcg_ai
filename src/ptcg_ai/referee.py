"""Implementation of the referee agent orchestrating the match."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .database import DatabaseClient
from .game_tools import GameTools, ToolCallContext
from .models import CardInstance, Deck, GameState, PlayerState, Zone
from .rulebook import RuleKnowledgeBase


@dataclass
class OperationRequest:
    """Structured request emitted by a player agent."""

    actor_id: str
    action: str
    payload: Dict[str, object]


@dataclass
class OperationResult:
    success: bool
    message: str
    data: Optional[Dict[str, object]] = None


@dataclass
class RefereeAgent:
    """High level orchestrator that enforces rules before calling tools."""

    referee_id: str
    knowledge_base: RuleKnowledgeBase
    database: DatabaseClient
    state: GameState
    tools: GameTools = field(init=False)

    def __post_init__(self) -> None:
        self.tools = GameTools(
            context=ToolCallContext(
                match_id=self.state.match_id,
                referee_id=self.referee_id,
                db=self.database,
            ),
            state=self.state,
        )

    # ------------------------------------------------------------------
    # match setup
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, match_id: str, player_decks: Dict[str, Deck], knowledge_base: RuleKnowledgeBase, database: Optional[DatabaseClient] = None) -> "RefereeAgent":
        for deck in player_decks.values():
            deck.validate()
        players = {
            player_id: PlayerState(player_id=player_id)
            for player_id in player_decks
        }
        state = GameState(match_id=match_id, players=players)
        db = database or DatabaseClient()
        referee = cls(
            referee_id="referee",
            knowledge_base=knowledge_base,
            database=db,
            state=state,
        )
        referee._initialise_decks(player_decks)
        return referee

    def _initialise_decks(self, player_decks: Dict[str, Deck]) -> None:
        for player_id, deck in player_decks.items():
            zone = self.state.players[player_id].zone(Zone.DECK)
            zone.cards[:] = list(deck.cards)
            self.tools.shuffle(player_id, Zone.DECK)
            prize_zone = self.state.players[player_id].zone(Zone.PRIZE)
            prize_zone.cards[:] = zone.cards[:6]
            del zone.cards[:6]
            self.database.persist_state(self.state)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def handle_request(self, request: OperationRequest) -> OperationResult:
        handler_name = f"_handle_{request.action}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            return OperationResult(False, f"Unknown action: {request.action}")
        try:
            result = handler(request.actor_id, **request.payload)
        except Exception as exc:  # noqa: BLE001 - we surface user facing errors
            return OperationResult(False, str(exc))
        self.database.persist_state(self.state)
        return OperationResult(True, "ok", data=result)

    # ------------------------------------------------------------------
    # handlers
    # ------------------------------------------------------------------
    def _handle_draw(self, actor_id: str, count: int) -> Dict[str, object]:
        self._ensure_turn(actor_id)
        cards = self.tools.draw(actor_id, count)
        return {"cards": [card.uid for card in cards]}

    def _handle_discard(self, actor_id: str, card_ids: Iterable[str], reason: str) -> Dict[str, object]:
        cards = self._locate_cards(actor_id, Zone.HAND, card_ids)
        self.tools.discard(actor_id, cards, reason)
        return {"discarded": list(card_ids)}

    def _handle_take_prize(self, actor_id: str, count: int = 1) -> Dict[str, object]:
        cards = self.tools.take_prize(actor_id, count)
        return {"cards": [card.uid for card in cards], "remaining": self.state.players[actor_id].prizes_remaining}

    def _handle_move_to_bench(self, actor_id: str, card_id: str) -> Dict[str, object]:
        card = self._locate_cards(actor_id, Zone.HAND, [card_id])[0]
        self.tools.move_card(actor_id, Zone.HAND, Zone.BENCH, card)
        return {"bench": [c.uid for c in self.state.players[actor_id].zone(Zone.BENCH).cards]}

    def _handle_query_rule(self, actor_id: str, query: str, limit: int = 3) -> Dict[str, object]:
        _ = actor_id  # For future access control checks
        matches = self.knowledge_base.find(query, limit=limit)
        return {
            "matches": [
                {
                    "section": entry.section,
                    "text": entry.text,
                }
                for entry in matches
            ]
        }

    # ------------------------------------------------------------------
    # helper functions
    # ------------------------------------------------------------------
    def _ensure_turn(self, actor_id: str) -> None:
        if self.state.turn_player is None:
            self.state.turn_player = actor_id
            self.state.turn_number = 1
            self.state.phase = "main"
            return
        if self.state.turn_player != actor_id:
            raise RuntimeError("It is not the requesting player's turn")

    def _locate_cards(self, player_id: str, zone: Zone, card_ids: Iterable[str]) -> List[CardInstance]:
        zone_state = self.state.players[player_id].zone(zone)
        lookup = {card.uid: card for card in zone_state.cards}
        try:
            return [lookup[card_id] for card_id in card_ids]
        except KeyError as exc:
            raise ValueError(f"Card {exc.args[0]} not present in {zone.value}") from exc


__all__ = ["RefereeAgent", "OperationRequest", "OperationResult"]
