"""Utility helpers to wire together agents for a simple simulation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from .card_loader import CardLibrary
from .models import Deck, Zone
from .player import PlayerAgent
from .referee import RefereeAgent
from .rulebook import RuleKnowledgeBase


def build_deck(owner_id: str, entries: Iterable[tuple[str, str, str]], library: CardLibrary) -> Deck:
    cards = library.instantiate(owner_id, entries)
    deck = Deck(player_id=owner_id, cards=cards)
    deck.validate()
    return deck


def load_rulebook_text(path: Path) -> RuleKnowledgeBase:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return RuleKnowledgeBase.from_text(text)


def run_turn(referee: RefereeAgent, players: Dict[str, PlayerAgent]) -> None:
    """Run a single turn loop where each player can submit one action."""

    for player_id, player in players.items():
        observation = {
            "hand_size": len(referee.state.players[player_id].zone(Zone.HAND).cards),
            "prizes": referee.state.players[player_id].prizes_remaining,
        }
        request = player.decide(observation)
        if request is None:
            continue
        result = referee.handle_request(request)
        player.memory.remember(f"Action {request.action} -> {result.message}")


__all__ = ["build_deck", "load_rulebook_text", "run_turn"]
