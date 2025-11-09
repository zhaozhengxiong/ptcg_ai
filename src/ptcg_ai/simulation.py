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
    # (count, set_code, number, card_name, line_number, original_line)
    card_requirements: List[tuple[int, str, str, str, int, str]] = []
    section = "Unknown"
    section_alias = {"Pokémon": "Pokemon"}
    parse_errors: List[str] = []

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_num, raw_line in enumerate(lines, start=1):
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
            error_msg = f"Malformed deck entry at line {line_num}: '{line}' (expected format: 'count Name SET_CODE NUMBER')"
            parse_errors.append(error_msg)
            raise ValueError(error_msg)

        try:
            count = int(parts[0])
        except ValueError as exc:  # pragma: no cover - defensive
            error_msg = f"Invalid card count at line {line_num}: '{line}' (first token must be a number)"
            parse_errors.append(error_msg)
            raise ValueError(error_msg) from exc

        set_code = parts[-2]
        number = parts[-1]
        # Extract card name (everything between count and set_code)
        card_name = " ".join(parts[1:-2]) if len(parts) > 3 else "Unknown"
        card_requirements.append((count, set_code, number, card_name, line_num, line))

    # Connect to database and query cards
    try:
        conn = psycopg.connect(dsn)
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to PostgreSQL: {exc}") from exc

    cards: List[CardInstance] = []
    card_definitions: Dict[tuple[str, str], CardDefinition] = {}
    failed_cards: List[Dict[str, object]] = []
    
    try:

        with conn.cursor() as cur:
            for count, set_code, number, card_name, line_num, original_line in card_requirements:
                # Check cache first
                key = (set_code, number)
                if key not in card_definitions:
                    # Try direct query first (backward compatible)
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

                    # Fallback: if direct query fails, try joining with ptcg_sets table
                    # This handles cases where set_ptcgo_code is NULL in ptcg_cards
                    if row is None:
                        cur.execute(
                            """
                            SELECT c.name, c.supertype, c.subtypes, c.hp, c.rules,
                                   COALESCE(c.set_ptcgo_code, s.ptcgo_code) as set_ptcgo_code,
                                   c.number, c.abilities, c.attacks
                            FROM ptcg_cards c
                            LEFT JOIN ptcg_sets s ON c.set_id = s.id
                            WHERE s.ptcgo_code = %s AND c.number = %s
                            LIMIT 1
                            """,
                            (set_code, number),
                        )
                        row = cur.fetchone()

                    if row is None:
                        error_info = {
                            "card_name": card_name,
                            "set_code": set_code,
                            "number": number,
                            "count": count,
                            "line_number": line_num,
                            "original_line": original_line,
                            "error": "Card not found in database"
                        }
                        failed_cards.append(error_info)
                        # Try to find similar cards for better error message
                        cur.execute(
                            """
                            SELECT name, set_ptcgo_code, number
                            FROM ptcg_cards
                            WHERE number = %s
                            LIMIT 5
                            """,
                            (number,),
                        )
                        similar_cards = cur.fetchall()
                        
                        error_msg = (
                            f"Card not found in database:\n"
                            f"  Location: @{path.name} ({line_num})\n"
                            f"  Card name (from deck file): {card_name}\n"
                            f"  Set code: {set_code}\n"
                            f"  Number: {number}\n"
                            f"  Count requested: {count}\n"
                            f"  Original line: {original_line}"
                        )
                        if similar_cards:
                            error_msg += f"\n  Similar cards found with number {number}:"
                            for sim_name, sim_set, sim_num in similar_cards:
                                error_msg += f"\n    - {sim_name} ({sim_set} {sim_num})"
                        else:
                            cur.execute(
                                """
                                SELECT name, set_ptcgo_code, number
                                FROM ptcg_cards
                                WHERE set_ptcgo_code = %s
                                LIMIT 5
                                """,
                                (set_code,),
                            )
                            same_set_cards = cur.fetchall()
                            if same_set_cards:
                                error_msg += f"\n  Cards found in set {set_code}:"
                                for sim_name, sim_set, sim_num in same_set_cards:
                                    error_msg += f"\n    - {sim_name} ({sim_set} {sim_num})"
                        
                        parse_errors.append(error_msg)
                        raise ValueError(error_msg)

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

    # Collect statistics before validation
    total_requested = sum(count for count, _, _, _, _, _ in card_requirements)
    total_loaded = len(cards)
    
    # Group cards by type for reporting
    card_type_counts: Dict[str, int] = {}
    for card in cards:
        card_type = card.definition.card_type
        card_type_counts[card_type] = card_type_counts.get(card_type, 0) + 1
    
    # Group failed cards by line ranges for compact display
    failed_by_range: Dict[tuple[int, int], List[Dict]] = {}
    for failed in failed_cards:
        line_num = failed['line_number']
        # Find or create range
        found_range = None
        for (start, end), cards_list in failed_by_range.items():
            if start <= line_num <= end:
                found_range = (start, end)
                break
        
        if found_range:
            failed_by_range[found_range].append(failed)
            # Update range if needed
            if line_num < found_range[0]:
                cards_list = failed_by_range.pop(found_range)
                failed_by_range[(line_num, found_range[1])] = cards_list
            elif line_num > found_range[1]:
                cards_list = failed_by_range.pop(found_range)
                failed_by_range[(found_range[0], line_num)] = cards_list
        else:
            failed_by_range[(line_num, line_num)] = [failed]
    
    # Validate deck
    try:
        deck = Deck(player_id=owner_id, cards=cards)
        deck.validate()
    except ValueError as e:
        # Print detailed error information
        print("\n" + "="*60)
        print("DECK PARSING ERROR")
        print("="*60)
        print(f"\nDeck file: {path}")
        print(f"Owner: {owner_id}")
        print(f"\nCard Statistics:")
        print(f"  Total cards requested: {total_requested}")
        print(f"  Total cards loaded: {total_loaded}")
        print(f"  Missing cards: {60 - total_loaded}")
        print(f"\nCards by type:")
        for card_type, count in sorted(card_type_counts.items()):
            print(f"  {card_type}: {count}")
        
        if failed_cards:
            print(f"\nFailed to load {len(failed_cards)} card type(s):")
            # Group by line ranges
            for (start_line, end_line), cards_list in sorted(failed_by_range.items()):
                if start_line == end_line:
                    location = f"@{path.name} ({start_line})"
                else:
                    location = f"@{path.name} ({start_line}-{end_line})"
                print(f"\n  {location}:")
                for failed in cards_list:
                    print(f"    - {failed['count']}x {failed['card_name']} ({failed['set_code']} {failed['number']})")
                    print(f"      Original line: {failed['original_line']}")
        
        if parse_errors:
            print(f"\nParse Errors ({len(parse_errors)}):")
            for i, error in enumerate(parse_errors, 1):
                print(f"\n  Error {i}:")
                print(f"  {error}")
        
        print("\n" + "="*60)
        raise
    
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
