#!/usr/bin/env python3
"""Fix database set fields using JSON metadata files from doc/cards/en.

This script:
1. Reads all JSON files from doc/cards/en/
2. Extracts set_id from filename (e.g., sv3pt5.json -> sv3pt5)
3. For each card in JSON, extracts set_id from card id (format: set_id-number)
4. Updates database cards with missing set_id, set_name, set_ptcgo_code from ptcg_sets table
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add parent directory to path to import ptcg_ai modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg
except ImportError:
    print("Error: psycopg is required. Install it with: pip install 'psycopg[binary]'")
    sys.exit(1)

from ptcg_ai.database import build_postgres_dsn


def extract_set_id_from_id(card_id: str) -> str | None:
    """Extract set_id from card id (format: set_id-number)."""
    if '-' in card_id:
        return card_id.split('-')[0]
    return None


def load_json_cards(json_dir: Path) -> Dict[str, List[Dict]]:
    """Load all JSON files and return a dict mapping set_id to cards."""
    sets_data: Dict[str, List[Dict]] = {}
    
    if not json_dir.exists():
        print(f"Error: JSON directory not found: {json_dir}")
        sys.exit(1)
    
    json_files = sorted(json_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    for json_file in json_files:
        set_id_from_filename = json_file.stem  # filename without .json extension
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            
            if not isinstance(cards, list):
                print(f"Warning: {json_file.name} does not contain a list, skipping")
                continue
            
            # Verify set_id consistency
            for card in cards:
                if 'id' in card:
                    set_id_from_card = extract_set_id_from_id(card['id'])
                    if set_id_from_card and set_id_from_card != set_id_from_filename:
                        print(f"Warning: Card {card['id']} has set_id {set_id_from_card} but file is {set_id_from_filename}.json")
            
            sets_data[set_id_from_filename] = cards
            print(f"  Loaded {len(cards)} cards from {json_file.name}")
            
        except Exception as e:
            print(f"Error loading {json_file.name}: {e}")
            continue
    
    return sets_data


def fix_database_from_json(json_dir: Path):
    """Fix database using JSON metadata."""
    # Load all JSON files
    print("Loading JSON files...")
    sets_data = load_json_cards(json_dir)
    
    if not sets_data:
        print("No JSON data loaded. Exiting.")
        sys.exit(1)
    
    # Build connection string
    dsn = build_postgres_dsn()
    print(f"\nConnecting to database...")
    print(f"DSN: {dsn.split('password=')[0]}password=***")
    
    try:
        conn = psycopg.connect(dsn)
    except Exception as e:
        print(f"Error: Failed to connect to PostgreSQL: {e}")
        print("\nMake sure you have set the correct environment variables:")
        print("  PGHOST (default: localhost)")
        print("  PGPORT (default: 5432)")
        print("  PGUSER (default: postgres)")
        print("  PGPASSWORD (default: postgres)")
        print("  PGDATABASE (default: ptcg)")
        sys.exit(1)
    
    try:
        with conn.cursor() as cur:
            # Step 1: Update set_id from card id field for cards where set_id is NULL
            print("\nStep 1: Updating set_id from id field...")
            cur.execute("""
                UPDATE ptcg_cards
                SET set_id = SPLIT_PART(id, '-', 1)
                WHERE set_id IS NULL
                  AND id LIKE '%-%'
            """)
            updated_count = cur.rowcount
            print(f"  Updated {updated_count} cards with set_id from id field")
            
            # Step 2: Collect all set_ids from JSON files and database
            json_set_ids = set(sets_data.keys())
            print(f"\nStep 2: Found {len(json_set_ids)} set_ids in JSON files")
            
            # Get set_ids from database cards
            cur.execute("SELECT DISTINCT set_id FROM ptcg_cards WHERE set_id IS NOT NULL")
            db_set_ids = {row[0] for row in cur.fetchall()}
            print(f"  Found {len(db_set_ids)} set_ids in database")
            
            # Step 3: Update set fields from ptcg_sets table
            print("\nStep 3: Updating set fields from ptcg_sets table...")
            cur.execute("""
                UPDATE ptcg_cards c
                SET 
                    set_name = s.name,
                    set_ptcgo_code = s.ptcgo_code,
                    set_series = s.series,
                    set_release_date = s.release_date,
                    set_printed_total = s.printed_total,
                    set_total = s.total,
                    set_updated_at = s.updated_at::text,
                    set_symbol_url = s.symbol_url,
                    set_logo_url = s.logo_url
                FROM ptcg_sets s
                WHERE c.set_id = s.id
                  AND (c.set_name IS NULL OR c.set_ptcgo_code IS NULL)
            """)
            updated_count = cur.rowcount
            print(f"  Updated {updated_count} cards with set information from ptcg_sets")
            
            # Step 4: Also update set_ptcgo_code for cards that have set_id but NULL set_ptcgo_code
            print("\nStep 4: Updating set_ptcgo_code for cards with set_id but NULL set_ptcgo_code...")
            cur.execute("""
                UPDATE ptcg_cards c
                SET set_ptcgo_code = s.ptcgo_code
                FROM ptcg_sets s
                WHERE c.set_id = s.id
                  AND c.set_ptcgo_code IS NULL
                  AND s.ptcgo_code IS NOT NULL
            """)
            updated_count = cur.rowcount
            print(f"  Updated {updated_count} cards with set_ptcgo_code")
            
            # Step 5: Verify and report
            print("\nStep 5: Verification...")
            cur.execute("""
                SELECT 
                    COUNT(*) as total_cards,
                    COUNT(CASE WHEN set_id IS NOT NULL THEN 1 END) as cards_with_set_id,
                    COUNT(CASE WHEN set_name IS NOT NULL THEN 1 END) as cards_with_set_name,
                    COUNT(CASE WHEN set_ptcgo_code IS NOT NULL THEN 1 END) as cards_with_set_ptcgo_code
                FROM ptcg_cards
            """)
            stats = cur.fetchone()
            print(f"  Total cards: {stats[0]}")
            print(f"  Cards with set_id: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
            print(f"  Cards with set_name: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
            print(f"  Cards with set_ptcgo_code: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
            
            # Check for remaining NULL values
            cur.execute("""
                SELECT COUNT(*) 
                FROM ptcg_cards 
                WHERE set_id IS NULL OR set_name IS NULL OR set_ptcgo_code IS NULL
            """)
            remaining_null = cur.fetchone()[0]
            if remaining_null > 0:
                print(f"\n  Warning: {remaining_null} cards still have NULL set fields")
                print("  Sample cards with NULL set fields:")
                cur.execute("""
                    SELECT id, name, number, set_id, set_name, set_ptcgo_code
                    FROM ptcg_cards
                    WHERE set_id IS NULL OR set_name IS NULL OR set_ptcgo_code IS NULL
                    LIMIT 10
                """)
                for row in cur.fetchall():
                    print(f"    {row}")
            else:
                print("\n  ✓ All cards have set information!")
            
            # Check for set_ids in JSON but not in ptcg_sets
            cur.execute("SELECT id FROM ptcg_sets")
            db_set_table_ids = {row[0] for row in cur.fetchall()}
            missing_in_sets_table = json_set_ids - db_set_table_ids
            if missing_in_sets_table:
                print(f"\n  Warning: {len(missing_in_sets_table)} set_ids from JSON not found in ptcg_sets table:")
                for set_id in sorted(missing_in_sets_table)[:10]:
                    print(f"    - {set_id}")
            
            conn.commit()
            print("\n✓ Database fix completed successfully!")
            
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    json_dir = Path(__file__).parent.parent / "doc" / "cards" / "en"
    fix_database_from_json(json_dir)

