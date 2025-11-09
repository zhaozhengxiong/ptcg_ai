"""Utilities to load card definitions from the official JSON dumps."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .models import CardDefinition, CardInstance


@dataclass
class CardLibrary:
    """Collection of card definitions indexed by (set_code, number)."""

    definitions: Dict[tuple[str, str], CardDefinition]

    @classmethod
    def from_json(cls, path: Path) -> "CardLibrary":
        data = json.loads(path.read_text(encoding="utf-8"))
        definitions = {}
        for card in data:
            key = (card["set"], card["number"])
            definitions[key] = CardDefinition(
                set_code=card["set"],
                number=card["number"],
                name=card["name"],
                card_type=card.get("type", "Unknown"),
                hp=int(card["hp"]) if card.get("hp") else None,
                stage=card.get("stage"),
                rules_text=card.get("rules_text"),
            )
        return cls(definitions)

    def instantiate(self, owner_id: str, entries: Iterable[tuple[str, str, str]]) -> List[CardInstance]:
        """Create card instances for the provided ``(uid, set, number)`` triples."""

        instances: List[CardInstance] = []
        for uid, set_code, number in entries:
            try:
                definition = self.definitions[(set_code, number)]
            except KeyError as exc:  # noqa: PERF203 - small loops
                raise ValueError(f"Card {set_code} {number} not found in library") from exc
            instances.append(CardInstance(uid=uid, owner_id=owner_id, definition=definition))
        return instances


__all__ = ["CardLibrary"]
