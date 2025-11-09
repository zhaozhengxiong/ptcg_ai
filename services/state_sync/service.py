"""State Sync service for async state management with optimistic locking."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

from src.ptcg_ai.database import DatabaseClient
from src.ptcg_ai.models import GameState

logger = logging.getLogger(__name__)


class StateSyncService:
    """Async state synchronization service with optimistic locking."""

    def __init__(self, db: DatabaseClient, pool: Optional[asyncpg.Pool] = None):
        """Initialize state sync service.
        
        Args:
            db: Database client (fallback for sync operations)
            pool: AsyncPG connection pool (optional)
        """
        self.db = db
        self.pool = pool

    async def persist_state_async(self, state: GameState, version: Optional[int] = None) -> bool:
        """Persist game state with optimistic locking.
        
        Args:
            state: Game state to persist
            version: Expected version number for optimistic locking
            
        Returns:
            True if successful, False if version conflict
        """
        if not self.pool:
            # Fallback to sync database client
            self.db.persist_state(state)
            return True

        async with self.pool.acquire() as conn:
            try:
                async with conn.transaction():
                    # Check version if provided
                    if version is not None:
                        current_version = await conn.fetchval(
                            "SELECT version FROM matches WHERE match_id = $1",
                            state.match_id,
                        )
                        if current_version != version:
                            logger.warning(
                                f"对局 {state.match_id} 版本冲突: "
                                f"期望 {version}，实际 {current_version}"
                            )
                            return False

                    # Update state
                    await conn.execute(
                        """
                        INSERT INTO matches (match_id, turn_player, turn_number, phase, snapshot, version, updated_at)
                        VALUES ($1, $2, $3, $4, $5, COALESCE((SELECT version FROM matches WHERE match_id = $1), 0) + 1, NOW())
                        ON CONFLICT (match_id) DO UPDATE SET
                            turn_player = EXCLUDED.turn_player,
                            turn_number = EXCLUDED.turn_number,
                            phase = EXCLUDED.phase,
                            snapshot = EXCLUDED.snapshot,
                            version = matches.version + 1,
                            updated_at = NOW()
                        """,
                        state.match_id,
                        state.turn_player,
                        state.turn_number,
                        state.phase,
                        state.snapshot(),
                    )
                    return True
            except Exception as e:
                logger.error(f"持久化状态时出错: {e}", exc_info=True)
                return False

    async def get_state_version(self, match_id: str) -> Optional[int]:
        """Get current version of game state.
        
        Args:
            match_id: Match identifier
            
        Returns:
            Version number or None if not found
        """
        if not self.pool:
            return None

        async with self.pool.acquire() as conn:
            version = await conn.fetchval(
                "SELECT version FROM matches WHERE match_id = $1",
                match_id,
            )
            return version


async def create_pool(dsn: str, min_size: int = 5, max_size: int = 20) -> Optional[asyncpg.Pool]:
    """Create asyncpg connection pool.
    
    Args:
        dsn: PostgreSQL connection string
        min_size: Minimum pool size
        max_size: Maximum pool size
        
    Returns:
        Connection pool or None if asyncpg not available
    """
    if asyncpg is None:
        logger.warning("asyncpg 不可用，使用同步数据库客户端")
        return None

    try:
        return await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    except Exception as e:
        logger.error(f"创建连接池失败: {e}", exc_info=True)
        return None

