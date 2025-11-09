#!/usr/bin/env python3
"""查询deck1.txt中所有卡牌的详细信息"""
import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg
except ImportError:
    try:
        import psycopg2 as psycopg
    except ImportError:
        print("Error: psycopg or psycopg2 is required")
        sys.exit(1)

def build_postgres_dsn():
    """Build PostgreSQL connection string from environment or defaults."""
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return dsn
    return "postgresql://postgres:postgres@localhost:5432/ptcg"

def query_card(set_code: str, number: str, dsn: str):
    """查询单张卡牌信息"""
    try:
        conn = psycopg.connect(dsn)
        with conn.cursor() as cur:
            # Try direct query first
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
            
            # Fallback: join with ptcg_sets table
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
                return None
            
            (
                name,
                supertype,
                subtypes,
                hp,
                rules,
                set_ptcgo_code,
                number,
                abilities,
                attacks,
            ) = row
            
            return {
                "name": name,
                "supertype": supertype,
                "subtypes": subtypes,
                "hp": hp,
                "rules": rules,
                "set_code": set_ptcgo_code,
                "number": number,
                "abilities": abilities,
                "attacks": attacks,
            }
    except Exception as e:
        print(f"Error querying {set_code} {number}: {e}")
        return None
    finally:
        conn.close()

def main():
    # Cards from deck1.txt that need analysis
    cards_to_query = [
        # Trainer cards
        ("PAF", "76", "Artazon"),
        ("AOR", "76", "Level Ball"),
        ("SIT", "156", "Forest Seal Stone"),
        ("SVI", "181", "Nest Ball"),
        ("ASR", "155", "Temple of Sinnoh"),
        ("OBF", "186", "Arven"),
        ("FST", "225", "Battle VIP Pass"),
        ("PAL", "172", "Boss's Orders"),
        ("PAL", "185", "Iono"),
        ("PAL", "188", "Super Rod"),
        ("LOR", "162", "Lost Vacuum"),
        ("BRS", "137", "Collapsed Stadium"),
        ("SVI", "196", "Ultra Ball"),
        ("SVI", "197", "Vitality Band"),
        ("SVI", "194", "Switch"),
        ("PRE", "121", "Professor Turo's Scenario"),
        ("SVI", "191", "Rare Candy"),
        # Energy
        ("SVE", "2", "Fire Energy"),
    ]
    
    dsn = build_postgres_dsn()
    results = {}
    
    for set_code, number, card_name in cards_to_query:
        print(f"Querying {card_name} {set_code} {number}...")
        card_info = query_card(set_code, number, dsn)
        if card_info:
            key = f"{card_info['name']} {set_code} {number}"
            results[key] = card_info
        else:
            print(f"  Warning: Could not find {card_name} {set_code} {number}")
    
    # Output results as JSON
    output_file = project_root / "doc" / "deck" / "deck_cards_info.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\nResults saved to {output_file}")
    print(f"Found {len(results)} cards")

if __name__ == "__main__":
    main()

