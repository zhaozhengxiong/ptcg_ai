-- Migration: Create base tables for matches and match_logs
-- This migration creates the foundational tables for the PTCG Agents system

-- Create matches table
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    turn_player TEXT,
    turn_number INT DEFAULT 0,
    phase TEXT DEFAULT 'init',
    snapshot JSONB,
    version INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create match_logs table
CREATE TABLE IF NOT EXISTS match_logs (
    id SERIAL PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    payload JSONB,
    random_seed BYTEA,
    timestamp TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_match_logs_match_id ON match_logs(match_id);
CREATE INDEX IF NOT EXISTS idx_match_logs_actor ON match_logs(actor);
CREATE INDEX IF NOT EXISTS idx_match_logs_action ON match_logs(action);
CREATE INDEX IF NOT EXISTS idx_match_logs_timestamp ON match_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_matches_updated_at ON matches(updated_at);

