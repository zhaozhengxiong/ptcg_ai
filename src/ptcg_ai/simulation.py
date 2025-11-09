"""Utility helpers to wire together agents for a simple simulation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .models import CardDefinition, CardInstance, Deck, Zone
from .player import PlayerAgent
from .referee import RefereeAgent
from .rulebook import RuleKnowledgeBase


def build_deck(owner_id: str, deck_file: str | Path) -> Deck:
    """Build a 60-card deck for ``owner_id`` using a text list similar to ``deck1.txt``."""

    path = Path(deck_file)
    if not path.is_file():
        raise FileNotFoundError(f"Deck file not found: {path}")

    cards: List[CardInstance] = []
    section = "Unknown"
    section_alias = {"Pokémon": "Pokemon"}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line and not line[0].isdigit():
            section = line.split(":", 1)[0].strip() or "Unknown"
            continue
        if not line[0].isdigit():
            continue

        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Malformed deck entry: '{line}'")

        try:
            count = int(parts[0])
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid card count in line: '{line}'") from exc

        set_code = parts[-2]
        number = parts[-1]
        name = " ".join(parts[1:-2])
        card_type = section_alias.get(section, section)

        definition = CardDefinition(
            set_code=set_code,
            number=number,
            name=name,
            card_type=card_type or "Unknown",
        )

        for _ in range(count):
            uid = f"{owner_id}-deck-{len(cards) + 1:03d}"
            cards.append(CardInstance(uid=uid, owner_id=owner_id, definition=definition))

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
