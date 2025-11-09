"""Vector search implementation for Rule Knowledge Base."""
from __future__ import annotations

import logging
from typing import List, Optional

try:
    import asyncpg
    from openai import OpenAI
except ImportError:
    asyncpg = None
    OpenAI = None

from src.ptcg_ai.rulebook import RuleEntry, RuleKnowledgeBase

logger = logging.getLogger(__name__)


class VectorRuleSearch:
    """Vector-based search for rules using embeddings."""

    def __init__(
        self,
        pool: Optional[asyncpg.Pool] = None,
        openai_client: Optional[OpenAI] = None,
        embedding_model: str = "text-embedding-3-large",
        similarity_threshold: float = 0.35,
    ):
        """Initialize vector search.
        
        Args:
            pool: AsyncPG connection pool
            openai_client: OpenAI client for embeddings
            embedding_model: Model to use for embeddings
            similarity_threshold: Cosine distance threshold (lower = more similar)
        """
        self.pool = pool
        self.client = openai_client or (OpenAI() if OpenAI else None)
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.fallback_kb: Optional[RuleKnowledgeBase] = None

    def set_fallback(self, kb: RuleKnowledgeBase):
        """Set fallback knowledge base for substring search."""
        self.fallback_kb = kb

    async def search(
        self,
        query: str,
        limit: int = 5,
        use_fallback: bool = True,
    ) -> List[RuleEntry]:
        """Search rules using vector similarity.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_fallback: Use substring search if vector search fails
            
        Returns:
            List of matching rule entries
        """
        if not self.pool or not self.client:
            # Fallback to substring search
            if use_fallback and self.fallback_kb:
                return self.fallback_kb.find(query, limit=limit)
            return []

        try:
            # Generate query embedding
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query,
            )
            query_embedding = response.data[0].embedding

            # Search using pgvector
            async with self.pool.acquire() as conn:
                # Use cosine distance (1 - cosine similarity)
                # Lower distance = more similar
                rows = await conn.fetch(
                    """
                    SELECT section, text, 
                           (embedding <=> $1::vector) as distance
                    FROM rule_embeddings
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    query_embedding,
                    limit * 2,  # Get more results to filter by threshold
                )

                results = []
                for row in rows:
                    distance = float(row["distance"])
                    if distance <= self.similarity_threshold:
                        results.append(RuleEntry(section=row["section"], text=row["text"]))
                        if len(results) >= limit:
                            break

                if results:
                    return results

        except Exception as e:
            logger.error(f"向量搜索出错: {e}", exc_info=True)

        # Fallback to substring search
        if use_fallback and self.fallback_kb:
            return self.fallback_kb.find(query, limit=limit)

        return []

    async def index_rules(self, kb: RuleKnowledgeBase) -> int:
        """Index rules from knowledge base into vector database.
        
        Args:
            kb: Rule knowledge base to index
            
        Returns:
            Number of rules indexed
        """
        if not self.pool or not self.client:
            logger.warning("无法索引规则：连接池或客户端不可用")
            return 0

        indexed = 0
        async with self.pool.acquire() as conn:
            # Create rule_embeddings table if it doesn't exist
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rule_embeddings (
                    section TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding vector(3072),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create index for vector search
            try:
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_rule_embeddings_vector
                    ON rule_embeddings USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            except Exception as e:
                logger.warning(f"无法创建向量索引: {e}")

            # Index each rule
            for entry in kb:
                try:
                    # Generate embedding
                    response = self.client.embeddings.create(
                        model=self.embedding_model,
                        input=entry.text,
                    )
                    embedding = response.data[0].embedding

                    # Store in database
                    await conn.execute(
                        """
                        INSERT INTO rule_embeddings (section, text, embedding)
                        VALUES ($1, $2, $3::vector)
                        ON CONFLICT (section) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding
                        """,
                        entry.section,
                        entry.text,
                        embedding,
                    )
                    indexed += 1
                except Exception as e:
                    logger.error(f"索引规则 {entry.section} 时出错: {e}", exc_info=True)

        logger.info(f"已索引 {indexed} 条规则")
        return indexed
