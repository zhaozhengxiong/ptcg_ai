# Database Migrations

This directory contains SQL migration scripts for the PTCG Agents database.

## Migration Files

- `001_add_memory_embeddings.sql` - Adds memory_embeddings table with pgvector support and enhances existing tables

## Running Migrations

Migrations should be run in order. You can apply them using:

```bash
psql -h localhost -U postgres -d ptcg -f db/migrations/001_add_memory_embeddings.sql
```

Or use a migration tool like Alembic (to be added in future).

