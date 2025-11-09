-- Fix NULL set_id, set_name, and set_ptcgo_code by extracting set_id from the id field
-- This script updates cards where set_id is NULL by parsing the id field (format: set_id-number)
-- and then populates set_name and set_ptcgo_code from the ptcg_sets table

-- Step 1: Update set_id from id field (extract part before the first hyphen)
UPDATE ptcg_cards
SET set_id = SPLIT_PART(id, '-', 1)
WHERE set_id IS NULL
  AND id LIKE '%-%';

-- Step 2: Update set_name and set_ptcgo_code by joining with ptcg_sets table
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
  AND (c.set_name IS NULL OR c.set_ptcgo_code IS NULL);

-- Step 3: Also update set_ptcgo_code for cards that have set_id but NULL set_ptcgo_code
UPDATE ptcg_cards c
SET set_ptcgo_code = s.ptcgo_code
FROM ptcg_sets s
WHERE c.set_id = s.id
  AND c.set_ptcgo_code IS NULL
  AND s.ptcgo_code IS NOT NULL;

-- Verify the fix: check some examples
SELECT 
    c.id,
    c.name,
    c.number,
    c.set_id,
    c.set_name,
    c.set_ptcgo_code,
    s.ptcgo_code as expected_ptcgo_code,
    s.name as expected_set_name
FROM ptcg_cards c
LEFT JOIN ptcg_sets s ON c.set_id = s.id
WHERE c.set_id IS NOT NULL
  AND (c.set_name IS NULL OR c.set_ptcgo_code IS NULL)
LIMIT 10;

-- Show summary of fixed records
SELECT 
    COUNT(*) as total_cards,
    COUNT(CASE WHEN set_id IS NOT NULL THEN 1 END) as cards_with_set_id,
    COUNT(CASE WHEN set_name IS NOT NULL THEN 1 END) as cards_with_set_name,
    COUNT(CASE WHEN set_ptcgo_code IS NOT NULL THEN 1 END) as cards_with_set_ptcgo_code
FROM ptcg_cards;

