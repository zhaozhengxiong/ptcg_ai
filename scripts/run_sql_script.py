#!/usr/bin/env python3
"""Run SQL scripts using the same connection logic as the application.

Usage:
    python scripts/run_sql_script.py <script_name>
    
Example:
    python scripts/run_sql_script.py fix_set_ptcgo_code.sql
    python scripts/run_sql_script.py fix_null_set_fields.sql
"""

import sys
from pathlib import Path

# Add parent directory to path to import ptcg_ai modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg
except ImportError:
    print("Error: psycopg is required. Install it with: pip install 'psycopg[binary]'")
    sys.exit(1)

from ptcg_ai.database import build_postgres_dsn


def run_sql_script(script_name: str):
    """Run a SQL script from the scripts directory."""
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"Error: SQL script not found at {script_path}")
        print(f"\nAvailable scripts:")
        for sql_file in Path(__file__).parent.glob("*.sql"):
            print(f"  - {sql_file.name}")
        sys.exit(1)
    
    # Build connection string using the same logic as the application
    dsn = build_postgres_dsn()
    
    print(f"Running SQL script: {script_name}")
    print(f"Connecting to database...")
    print(f"DSN: {dsn.split('password=')[0]}password=***")  # Hide password in output
    
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
            # Read and execute the SQL script
            sql_content = script_path.read_text(encoding="utf-8")
            
            # Remove comments and split by semicolons
            lines = []
            for line in sql_content.split('\n'):
                # Remove inline comments
                if '--' in line:
                    line = line[:line.index('--')]
                lines.append(line)
            
            # Join lines and split by semicolons
            full_sql = '\n'.join(lines)
            statements = [s.strip() for s in full_sql.split(';') if s.strip()]
            
            print(f"\nExecuting {len(statements)} SQL statement(s)...")
            
            for i, statement in enumerate(statements, 1):
                if statement:
                    try:
                        cur.execute(statement)
                        if statement.strip().upper().startswith('SELECT'):
                            # For SELECT statements, fetch and display results
                            rows = cur.fetchall()
                            if rows:
                                print(f"\nQuery {i} results ({len(rows)} row(s)):")
                                # Get column names if available
                                if cur.description:
                                    colnames = [desc[0] for desc in cur.description]
                                    print(f"  Columns: {', '.join(colnames)}")
                                for row in rows:
                                    print(f"  {row}")
                            else:
                                print(f"\nQuery {i}: No results")
                        else:
                            # For UPDATE/INSERT/DELETE, show affected rows
                            affected = cur.rowcount
                            print(f"Query {i}: {affected} row(s) affected")
                    except Exception as e:
                        print(f"Error executing query {i}: {e}")
                        print(f"Statement: {statement[:200]}...")
                        raise
            
            conn.commit()
            print("\n✓ Script executed successfully!")
            
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error executing script: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_sql_script.py <script_name>")
        print("\nAvailable scripts:")
        for sql_file in Path(__file__).parent.glob("*.sql"):
            print(f"  - {sql_file.name}")
        sys.exit(1)
    
    script_name = sys.argv[1]
    run_sql_script(script_name)

