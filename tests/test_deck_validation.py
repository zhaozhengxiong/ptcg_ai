from __future__ import annotations

import pytest

from ptcg_ai.models import CardDefinition, CardInstance, Deck


def _build_cards(count: int) -> list[CardInstance]:
    definition = CardDefinition(set_code="SVE", number="001", name="Test", card_type="Pokemon")
    return [CardInstance(uid=f"player-deck-{i:03d}", owner_id="player", definition=definition) for i in range(count)]


def test_valid_deck_passes_validation() -> None:
    deck = Deck(player_id="player", cards=_build_cards(60))
    deck.validate()


def test_invalid_size_raises() -> None:
    deck = Deck(player_id="player", cards=_build_cards(59))
    with pytest.raises(ValueError):
        deck.validate()


def test_duplicate_uid_raises() -> None:
    cards = _build_cards(60)
    cards[0] = CardInstance(uid="duplicate", owner_id="player", definition=cards[0].definition)
    cards[1] = CardInstance(uid="duplicate", owner_id="player", definition=cards[1].definition)
    deck = Deck(player_id="player", cards=cards)
    with pytest.raises(ValueError):
        deck.validate()
