"""Utilities to load card definitions from the official JSON dumps or PostgreSQL."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .database import build_postgres_dsn
from .models import CardDefinition, CardInstance

try:  # pragma: no cover - optional dependency
    import psycopg
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore


def _extract_stage_from_subtypes(subtypes: Optional[List[str]]) -> Optional[str]:
    """Extract stage information from subtypes array for Pokémon cards.
    
    Looks for "Basic", "Stage 1", or "Stage 2" in the subtypes array.
    
    Args:
        subtypes: List of subtype strings from database.
    
    Returns:
        Stage string ("Basic", "Stage 1", "Stage 2") or None if not found.
    """
    if not subtypes:
        return None
    
    stage_keywords = ["Basic", "Stage 1", "Stage 2"]
    for keyword in stage_keywords:
        if keyword in subtypes:
            return keyword
    
    return None


def _parse_postgres_array(value: Any) -> Optional[List[str]]:
    """Parse PostgreSQL array type to Python list.
    
    Args:
        value: PostgreSQL array value (could be list, tuple, or string).
    
    Returns:
        List of strings or None if value is None/empty.
    """
    if value is None:
        return None
    
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    
    if isinstance(value, str):
        # Handle string representation of array
        if value.startswith("{") and value.endswith("}"):
            # PostgreSQL array format: {item1,item2,item3}
            content = value[1:-1]
            if not content.strip():
                return None
            return [item.strip().strip('"') for item in content.split(",") if item.strip()]
        return [value]
    
    return None


def _parse_jsonb(value: Any) -> Optional[List[Dict[str, object]]]:
    """Parse PostgreSQL JSONB field to Python list of dicts.
    
    Args:
        value: JSONB value (could be dict, list, or string).
    
    Returns:
        List of dictionaries or None if value is None/empty.
    """
    if value is None:
        return None
    
    if isinstance(value, list):
        # Already a list, ensure all items are dicts
        return [item if isinstance(item, dict) else {} for item in value]
    
    if isinstance(value, dict):
        # Single dict, wrap in list
        return [value]
    
    if isinstance(value, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [item if isinstance(item, dict) else {} for item in parsed]
            if isinstance(parsed, dict):
                return [parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    
    return None


def _map_card_fields(
    db_name: str,
    db_supertype: Optional[str],
    db_subtypes: Any,
    db_hp: Optional[int],
    db_rules: Any,
    db_set_code: str,
    db_number: str,
    db_abilities: Any = None,
    db_attacks: Any = None,
) -> CardDefinition:
    """Map database fields to CardDefinition based on supertype.
    
    Args:
        db_name: Card name from database.
        db_supertype: Supertype (Pokémon, Trainer, Energy).
        db_subtypes: Subtypes array from database.
        db_hp: HP value (typically only for Pokémon).
        db_rules: Rules array from database.
        db_set_code: Set code from database.
        db_number: Card number from database.
        db_abilities: Abilities JSONB (typically only for Pokémon).
        db_attacks: Attacks JSONB (typically only for Pokémon).
    
    Returns:
        CardDefinition instance with mapped fields.
    """
    # Map supertype to card_type
    card_type = db_supertype or "Unknown"
    if card_type == "Pokémon":
        card_type = "Pokemon"
    
    # Parse subtypes array
    subtypes_list = _parse_postgres_array(db_subtypes)
    
    # Extract stage from subtypes (for Pokémon)
    stage = None
    if card_type == "Pokemon" and subtypes_list:
        stage = _extract_stage_from_subtypes(subtypes_list)
    
    # Convert rules array to string
    rules_text = None
    if db_rules:
        if isinstance(db_rules, list):
            rules_text = " ".join(str(r) for r in db_rules if r)
        else:
            rules_text = str(db_rules)
    
    # Parse abilities and attacks (JSONB fields)
    abilities = _parse_jsonb(db_abilities) if db_abilities else None
    attacks = _parse_jsonb(db_attacks) if db_attacks else None
    
    return CardDefinition(
        set_code=db_set_code,
        number=db_number,
        name=db_name,
        card_type=card_type,
        hp=db_hp,
        stage=stage,
        rules_text=rules_text,
        subtypes=subtypes_list,
        abilities=abilities,
        attacks=attacks,
    )


@dataclass
class CardLibrary:
    """Collection of card definitions indexed by (set_code, number)."""

    definitions: Dict[tuple[str, str], CardDefinition]

    @classmethod
    def from_json(cls, path: Path) -> "CardLibrary":
        """Load card definitions from JSON file.
        
        .. deprecated:: 
            This method loads from JSON files. Consider using from_postgres() instead
            to load from PostgreSQL database.
        """
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

    @classmethod
    def from_postgres(cls, dsn: Optional[str] = None) -> "CardLibrary":
        """Load all card definitions from PostgreSQL ptcg_cards table.
        
        Args:
            dsn: Optional PostgreSQL connection string. If not provided, uses build_postgres_dsn().
        
        Returns:
            CardLibrary instance with all cards from the database.
        
        Raises:
            RuntimeError: If database connection fails or psycopg is not available.
        """
        if psycopg is None:
            raise RuntimeError(
                "psycopg is required to load card data from PostgreSQL. "
                "Install it with: pip install 'psycopg[binary]'"
            )

        if dsn is None:
            dsn = build_postgres_dsn()

        try:
            conn = psycopg.connect(dsn)
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to PostgreSQL: {exc}") from exc

        definitions: Dict[tuple[str, str], CardDefinition] = {}

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT name, supertype, subtypes, hp, rules, set_ptcgo_code, number,
                           abilities, attacks
                    FROM ptcg_cards
                    WHERE set_ptcgo_code IS NOT NULL AND number IS NOT NULL
                    """
                )
                rows = cur.fetchall()

                for row in rows:
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

                    if not db_set_code or not db_number:
                        continue

                    # Use helper function to map all fields
                    definition = _map_card_fields(
                        db_name=db_name,
                        db_supertype=db_supertype,
                        db_subtypes=db_subtypes,
                        db_hp=db_hp,
                        db_rules=db_rules,
                        db_set_code=db_set_code,
                        db_number=db_number,
                        db_abilities=db_abilities,
                        db_attacks=db_attacks,
                    )

                    key = (db_set_code, db_number)
                    definitions[key] = definition

        finally:
            conn.close()

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
