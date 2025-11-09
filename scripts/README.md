# Database Fix Scripts

## fix_set_ptcgo_code.sql

This script fixes NULL values in the `set_ptcgo_code` column of the `ptcg_cards` table by joining with the `ptcg_sets` table.

### Usage Options

#### Option 1: Using Python script (Recommended)

Use the provided Python script that uses the same connection logic as the application:

```bash
python scripts/run_fix_script.py
```

This script uses the same environment variables as the application (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE).

#### Option 2: Using psql with environment variables

Set the environment variables and use psql:

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=postgres
export PGDATABASE=ptcg

psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f scripts/fix_set_ptcgo_code.sql
```

#### Option 3: Using connection string

If you have a PostgreSQL connection string:

```bash
psql "postgresql://user:password@host:port/database" -f scripts/fix_set_ptcgo_code.sql
```

#### Option 4: Fix peer authentication issue

If you get "Peer authentication failed", you can either:

1. Switch to password authentication by editing `/etc/postgresql/*/main/pg_hba.conf`:
   ```
   local   all             postgres                                md5
   ```
   Then restart PostgreSQL: `sudo systemctl restart postgresql`

2. Or use the Python script (Option 1) which handles authentication automatically.

### What it does

1. Updates all cards where `set_ptcgo_code IS NULL` by getting the correct `ptcgo_code` from the `ptcg_sets` table
2. Verifies the fix by checking if MEW set cards (sv3pt5) are now properly updated

### Note

Even without running this script, the application should work correctly due to the fallback query logic implemented in `build_deck()`. However, running this script is recommended to fix the data at the source and improve query performance.

## fix_null_set_fields.sql

This script fixes NULL values in `set_id`, `set_name`, and `set_ptcgo_code` by extracting `set_id` from the `id` field and joining with the `ptcg_sets` table.

### Usage

```bash
python scripts/run_sql_script.py fix_null_set_fields.sql
```

## fix_database_from_json.py (Recommended)

This comprehensive script fixes database set fields using JSON metadata files from `doc/cards/en/`. It:

1. Reads all JSON files from `doc/cards/en/`
2. Extracts set_id from filenames (e.g., `sv3pt5.json` -> `sv3pt5`)
3. Updates database cards with missing set information from `ptcg_sets` table
4. Provides detailed statistics and verification

### Usage

```bash
python scripts/fix_database_from_json.py
```

This script uses the same environment variables as the application and provides comprehensive reporting on what was fixed.

### What it does

1. Updates `set_id` from card `id` field (format: `set_id-number`) for cards where `set_id` is NULL
2. Updates `set_name`, `set_ptcgo_code`, and other set fields by joining with `ptcg_sets` table
3. Verifies the fix and reports statistics
4. Warns about any remaining issues or missing set_ids

This is the recommended approach as it uses the authoritative JSON metadata files as the source of truth.

