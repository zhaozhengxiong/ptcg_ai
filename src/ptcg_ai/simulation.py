"""Utility helpers to wire together agents for a simple simulation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .card_loader import _map_card_fields
from .database import build_postgres_dsn
from .models import CardDefinition, CardInstance, Deck, Zone
from .player import PlayerAgent
from .referee import RefereeAgent
from .rulebook import RuleKnowledgeBase

try:  # pragma: no cover - optional dependency
    import psycopg
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore


def build_deck(owner_id: str, deck_file: str | Path, dsn: Optional[str] = None) -> Deck:
    """Build a 60-card deck for ``owner_id`` using a text list similar to ``deck1.txt``.
    
    Card data is loaded from PostgreSQL ptcg_cards table using set_code (ptcgo_code) and number.
    
    Args:
        owner_id: Identifier for the deck owner.
        deck_file: Path to the deck file.
        dsn: Optional PostgreSQL connection string. If not provided, uses build_postgres_dsn().
    
    Returns:
        A validated Deck instance with 60 cards.
    
    Raises:
        FileNotFoundError: If deck file doesn't exist.
        ValueError: If deck file is malformed or cards are not found in database.
        RuntimeError: If database connection fails or psycopg is not available.
    """

    if psycopg is None:
        raise RuntimeError(
            "psycopg is required to load card data from PostgreSQL. "
            "Install it with: pip install 'psycopg[binary]'"
        )

    path = Path(deck_file)
    if not path.is_file():
        raise FileNotFoundError(f"Deck file not found: {path}")

    # Build connection string
    if dsn is None:
        dsn = build_postgres_dsn()

    # Parse deck file to collect card requirements
    card_requirements: List[tuple[int, str, str]] = []  # (count, set_code, number)
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
        card_requirements.append((count, set_code, number))

    # Connect to database and query cards
    try:
        conn = psycopg.connect(dsn)
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to PostgreSQL: {exc}") from exc

    try:
        cards: List[CardInstance] = []
        card_definitions: Dict[tuple[str, str], CardDefinition] = {}

        with conn.cursor() as cur:
            for count, set_code, number in card_requirements:
                # Check cache first
                key = (set_code, number)
                if key not in card_definitions:
                    # Query database for card
                    cur.execute(
                        """
                        SELECT name, supertype, subtypes, hp, rules, set_ptcgo_code, number,
                               abilities, attacks
                        FROM ptcg_cards
                        WHERE set_ptcgo_code = %s AND number = %s
                        LIMIT 1
                        """,
                        (set_code, number),
                    )
                    row = cur.fetchone()

                    if row is None:
                        raise ValueError(
                            f"Card not found in database: set_code={set_code}, number={number}"
                        )

                    (
                        db_name,
                        db_supertype,
                        db_subtypes,
                        db_hp,
                        db_rules,
                        db_set_code,
                        db_number,
                        db_abilities,
                        db_attacks,
                    ) = row

                    # Use helper function to map all fields
                    definition = _map_card_fields(
                        db_name=db_name,
                        db_supertype=db_supertype,
                        db_subtypes=db_subtypes,
                        db_hp=db_hp,
                        db_rules=db_rules,
                        db_set_code=db_set_code or set_code,
                        db_number=db_number or number,
                        db_abilities=db_abilities,
                        db_attacks=db_attacks,
                    )
                    card_definitions[key] = definition

                definition = card_definitions[key]

                # Create card instances
                for _ in range(count):
                    uid = f"{owner_id}-deck-{len(cards) + 1:03d}"
                    cards.append(CardInstance(uid=uid, owner_id=owner_id, definition=definition))

    finally:
        conn.close()

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
