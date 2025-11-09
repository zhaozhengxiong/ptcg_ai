"""Memory Store service for agent memories with embeddings."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

try:
    import asyncpg
    from openai import OpenAI
except ImportError:
    asyncpg = None
    OpenAI = None

logger = logging.getLogger(__name__)


class MemoryStore:
    """Service for storing and retrieving agent memories with embeddings."""

    def __init__(
        self,
        pool: Optional[asyncpg.Pool] = None,
        openai_client: Optional[OpenAI] = None,
        embedding_model: str = "text-embedding-3-large",
        similarity_threshold: float = 0.35,
        compression_interval: int = 10,
    ):
        """Initialize memory store.
        
        Args:
            pool: AsyncPG connection pool
            openai_client: OpenAI client for embeddings and summarization
            embedding_model: Model for embeddings
            similarity_threshold: Cosine distance threshold for retrieval
            compression_interval: Number of events before compression
        """
        self.pool = pool
        self.client = openai_client or (OpenAI() if OpenAI else None)
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.compression_interval = compression_interval

    async def store_memory(
        self,
        agent_id: str,
        uid: str,
        content: str,
        metadata: Optional[Dict] = None,
        match_id: Optional[str] = None,
        turn_number: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> bool:
        """Store a memory with embedding.
        
        Args:
            agent_id: Agent identifier
            uid: Unique identifier for the memory
            content: Memory content
            metadata: Optional metadata
            match_id: Match identifier
            turn_number: Turn number
            event_type: Type of event
            
        Returns:
            True if successful
        """
        if not self.pool:
            logger.warning("无法存储记忆：连接池不可用")
            return False

        try:
            # Generate embedding
            embedding = None
            if self.client:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=content,
                )
                embedding = response.data[0].embedding

            # Store in database
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_embeddings 
                    (agent_id, uid, content, embedding, metadata, match_id, turn_number, event_type)
                    VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8)
                    ON CONFLICT (uid) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    agent_id,
                    uid,
                    content,
                    embedding,
                    json.dumps(metadata) if metadata else None,
                    match_id,
                    turn_number,
                    event_type,
                )

            # Check if compression is needed
            await self._check_compression(agent_id, match_id)

            return True
        except Exception as e:
            logger.error(f"存储记忆时出错: {e}", exc_info=True)
            return False

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str,
        limit: int = 5,
        match_id: Optional[str] = None,
    ) -> List[Dict]:
        """Retrieve memories using semantic search.
        
        Args:
            agent_id: Agent identifier
            query: Query string
            limit: Maximum number of results
            match_id: Optional match filter
            
        Returns:
            List of memory dictionaries
        """
        if not self.pool or not self.client:
            # Fallback to recent memories
            return await self._get_recent_memories(agent_id, limit, match_id)

        try:
            # Generate query embedding
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query,
            )
            query_embedding = response.data[0].embedding

            # Search using pgvector
            async with self.pool.acquire() as conn:
                sql = """
                    SELECT uid, content, metadata, match_id, turn_number, event_type,
                           (embedding <=> $1::vector) as distance
                    FROM memory_embeddings
                    WHERE agent_id = $2
                      AND archived = FALSE
                      AND embedding IS NOT NULL
                """
                params = [query_embedding, agent_id]

                if match_id:
                    sql += " AND match_id = $3"
                    params.append(match_id)

                sql += """
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                """
                params.append(limit * 2)  # Get more to filter by threshold

                rows = await conn.fetch(sql, *params)

                results = []
                for row in rows:
                    distance = float(row["distance"])
                    if distance <= self.similarity_threshold:
                        results.append({
                            "uid": row["uid"],
                            "content": row["content"],
                            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                            "match_id": row["match_id"],
                            "turn_number": row["turn_number"],
                            "event_type": row["event_type"],
                            "distance": distance,
                        })
                        if len(results) >= limit:
                            break

                if results:
                    return results

        except Exception as e:
            logger.error(f"检索记忆时出错: {e}", exc_info=True)

        # Fallback to recent memories
        return await self._get_recent_memories(agent_id, limit, match_id)

    async def _get_recent_memories(
        self,
        agent_id: str,
        limit: int,
        match_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get recent memories as fallback."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                sql = """
                    SELECT uid, content, metadata, match_id, turn_number, event_type
                    FROM memory_embeddings
                    WHERE agent_id = $1 AND archived = FALSE
                """
                params = [agent_id]

                if match_id:
                    sql += " AND match_id = $2"
                    params.append(match_id)

                sql += " ORDER BY created_at DESC LIMIT $3"
                params.append(limit)

                rows = await conn.fetch(sql, *params)
                return [
                    {
                        "uid": row["uid"],
                        "content": row["content"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                        "match_id": row["match_id"],
                        "turn_number": row["turn_number"],
                        "event_type": row["event_type"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"获取最近记忆时出错: {e}", exc_info=True)
            return []

    async def _check_compression(self, agent_id: str, match_id: Optional[str] = None):
        """Check if compression is needed and perform it."""
        if not self.pool or not self.client:
            return

        try:
            async with self.pool.acquire() as conn:
                # Count recent unarchived memories
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM memory_embeddings
                    WHERE agent_id = $1 AND archived = FALSE
                    """ + (" AND match_id = $2" if match_id else ""),
                    agent_id,
                    *(match_id,) if match_id else (),
                )

                if count >= self.compression_interval:
                    await self._compress_memories(agent_id, match_id)
        except Exception as e:
            logger.error(f"检查压缩时出错: {e}", exc_info=True)

    async def _compress_memories(self, agent_id: str, match_id: Optional[str] = None):
        """Compress recent memories into a summary."""
        if not self.pool or not self.client:
            return

        try:
            async with self.pool.acquire() as conn:
                # Get recent memories
                sql = """
                    SELECT content, metadata, match_id, turn_number, event_type
                    FROM memory_embeddings
                    WHERE agent_id = $1 AND archived = FALSE
                """
                params = [agent_id]

                if match_id:
                    sql += " AND match_id = $2"
                    params.append(match_id)

                sql += " ORDER BY created_at DESC LIMIT $3"
                params.append(self.compression_interval)

                rows = await conn.fetch(sql, *params)

                if not rows:
                    return

                # Create summary using GPT-4
                memories_text = "\n".join([
                    f"Turn {row['turn_number']}: {row['content']}"
                    for row in rows
                ])

                response = self.client.chat.completions.create(
                    model="gpt-4o",  # Use gpt-4o or gpt-4-turbo (available models)
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize these game memories into a concise summary focusing on key decisions, strategies, and outcomes.",
                        },
                        {
                            "role": "user",
                            "content": memories_text,
                        },
                    ],
                )

                summary = response.choices[0].message.content

                # Generate embedding for summary
                embedding_response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=summary,
                )
                embedding = embedding_response.data[0].embedding

                # Store summary
                summary_uid = f"{agent_id}-summary-{datetime.utcnow().isoformat()}"
                await conn.execute(
                    """
                    INSERT INTO memory_embeddings
                    (agent_id, uid, content, embedding, metadata, match_id, archived)
                    VALUES ($1, $2, $3, $4::vector, $5, $6, FALSE)
                    """,
                    agent_id,
                    summary_uid,
                    summary,
                    embedding,
                    json.dumps({"type": "summary", "compressed_from": len(rows)}),
                    match_id,
                )

                # Archive original memories
                await conn.execute(
                    """
                    UPDATE memory_embeddings
                    SET archived = TRUE
                    WHERE agent_id = $1 AND archived = FALSE
                    """ + (" AND match_id = $2" if match_id else ""),
                    agent_id,
                    *(match_id,) if match_id else (),
                )

                logger.info(f"已将 {len(rows)} 条记忆压缩为摘要，代理ID: {agent_id}")
        except Exception as e:
            logger.error(f"压缩记忆时出错: {e}", exc_info=True)

