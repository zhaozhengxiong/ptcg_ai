-- Fix set_ptcgo_code NULL values by joining with ptcg_sets table
-- This script updates all cards where set_ptcgo_code is NULL
-- by getting the correct ptcgo_code from the ptcg_sets table

UPDATE ptcg_cards
SET set_ptcgo_code = ptcg_sets.ptcgo_code
FROM ptcg_sets
WHERE ptcg_cards.set_id = ptcg_sets.id
  AND ptcg_cards.set_ptcgo_code IS NULL
  AND ptcg_sets.ptcgo_code IS NOT NULL;

-- Verify the fix: check if MEW set cards are now updated
SELECT 
    c.id,
    c.name,
    c.number,
    c.set_id,
    c.set_ptcgo_code,
    s.ptcgo_code as expected_ptcgo_code
FROM ptcg_cards c
JOIN ptcg_sets s ON c.set_id = s.id
WHERE c.set_id = 'sv3pt5'
  AND c.number = '16'
LIMIT 5;

