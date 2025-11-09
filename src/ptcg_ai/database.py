"""Database access helpers for persisting games and logs."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .models import CardInstance, GameLogEntry, GameState, Zone

try:  # pragma: no cover - optional dependency
    import psycopg
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore


def build_postgres_dsn() -> str:
    """Build PostgreSQL DSN from environment variables.
    
    Reads the following environment variables:
    - PGHOST (default: localhost)
    - PGPORT (default: 5432)
    - PGUSER (default: postgres)
    - PGPASSWORD (default: postgres)
    - PGDATABASE (default: ptcg)
    
    Returns:
        PostgreSQL connection string in libpq format.
    """
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")
    database = os.getenv("PGDATABASE", "ptcg")
    
    return f"host={host} port={port} user={user} password={password} dbname={database}"


@dataclass
class InMemoryDatabase:
    """Fallback store used for testing and local development."""

    matches: Dict[str, GameState] = field(default_factory=dict)
    logs: Dict[str, List[GameLogEntry]] = field(default_factory=dict)

    def write_state(self, state: GameState) -> None:
        self.matches[state.match_id] = state

    def append_log(self, entry: GameLogEntry) -> None:
        self.logs.setdefault(entry.match_id, []).append(entry)

    def iter_logs(self, match_id: str) -> Iterable[GameLogEntry]:
        yield from self.logs.get(match_id, [])


class DatabaseClient:
    """Thin wrapper around PostgreSQL operations.

    The class is intentionally conservative: if psycopg or a DSN is not
    available we fall back to the in-memory store, ensuring the engine remains
    testable without external infrastructure. When backed by PostgreSQL we
    store each log entry inside ``match_logs`` and the full state snapshot in
    ``matches``.
    """

    def __init__(self, dsn: Optional[str] = None, memory_store: Optional[InMemoryDatabase] = None) -> None:
        self._dsn = dsn
        self._memory = memory_store or InMemoryDatabase()
        self._conn = None
        if dsn and psycopg is not None:
            self._conn = psycopg.connect(dsn)  # pragma: no cover - integration path

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------
    def persist_state(self, state: GameState) -> None:
        if self._conn is None:
            self._memory.write_state(state)
            return

        with self._conn.cursor() as cur:  # pragma: no cover - integration path
            cur.execute(
                """
                INSERT INTO matches (match_id, turn_player, turn_number, phase, snapshot, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE SET
                    turn_player = EXCLUDED.turn_player,
                    turn_number = EXCLUDED.turn_number,
                    phase = EXCLUDED.phase,
                    snapshot = EXCLUDED.snapshot,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    state.match_id,
                    state.turn_player,
                    state.turn_number,
                    state.phase,
                    state.snapshot(),
                    datetime.utcnow(),
                ),
            )
            self._conn.commit()

    def append_log(self, entry: GameLogEntry) -> None:
        if self._conn is None:
            self._memory.append_log(entry)
            return

        with self._conn.cursor() as cur:  # pragma: no cover - integration path
            cur.execute(
                """
                INSERT INTO match_logs (match_id, actor, action, payload, random_seed, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    entry.match_id,
                    entry.actor,
                    entry.action,
                    entry.payload,
                    entry.random_seed,
                    datetime.utcnow(),
                ),
            )
            self._conn.commit()

    def record_zone(self, match_id: str, player_id: str, zone: Zone, cards: Iterable[CardInstance]) -> None:
        """Persist the content of a zone for auditing purposes."""

        payload = {
            "player_id": player_id,
            "zone": zone.value,
            "cards": [card.uid for card in cards],
        }
        self.append_log(
            GameLogEntry(
                match_id=match_id,
                actor="system",
                action="zone_snapshot",
                payload=payload,
            )
        )

    # ------------------------------------------------------------------
    # read helpers
    # ------------------------------------------------------------------
    def get_logs(self, match_id: str) -> List[GameLogEntry]:
        if self._conn is None:
            return list(self._memory.iter_logs(match_id))

        with self._conn.cursor() as cur:  # pragma: no cover - integration path
            cur.execute(
                """
                SELECT match_id, actor, action, payload, random_seed
                FROM match_logs
                WHERE match_id = %s
                ORDER BY created_at ASC
                """,
                (match_id,),
            )
            rows = cur.fetchall()
        return [GameLogEntry(*row) for row in rows]


__all__ = ["DatabaseClient", "InMemoryDatabase", "build_postgres_dsn"]
