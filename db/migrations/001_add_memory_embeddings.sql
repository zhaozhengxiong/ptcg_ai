-- Migration: Add memory_embeddings table with pgvector support
-- This migration adds the memory_embeddings table for storing agent memories with vector embeddings

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create memory_embeddings table
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(3072),  -- For text-embedding-3-large
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE,
    match_id TEXT,
    turn_number INT,
    event_type TEXT
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_agent_id ON memory_embeddings(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_match_id ON memory_embeddings(match_id);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_archived ON memory_embeddings(archived);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_created_at ON memory_embeddings(created_at);

-- Create vector similarity search index (IVFFlat for approximate nearest neighbor)
-- Note: This index requires at least some data to be effective
-- The index will be created after data is loaded
-- CREATE INDEX idx_memory_embeddings_vector ON memory_embeddings 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Add version column to matches table for optimistic locking
ALTER TABLE matches ADD COLUMN IF NOT EXISTS version INT DEFAULT 0;

-- Enhance match_logs table if needed
ALTER TABLE match_logs ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT NOW();

