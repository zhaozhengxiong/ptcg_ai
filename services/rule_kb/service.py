"""Rule Knowledge Base service."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.ptcg_ai.rulebook import RuleEntry, RuleKnowledgeBase

logger = logging.getLogger(__name__)

app = FastAPI(title="Rule Knowledge Base Service")


class RuleQueryRequest(BaseModel):
    """Request for rule query."""
    query: str
    limit: int = 5


class RuleMatch(BaseModel):
    """Rule match result."""
    section: str
    text: str


class RuleQueryResponse(BaseModel):
    """Response for rule query."""
    matches: List[RuleMatch]


class RuleKBService:
    """Rule Knowledge Base service implementation."""

    def __init__(self, knowledge_base: RuleKnowledgeBase):
        """Initialize service.
        
        Args:
            knowledge_base: Rule knowledge base instance
        """
        self.kb = knowledge_base

    def query(self, query: str, limit: int = 5) -> List[RuleMatch]:
        """Query rules.
        
        Args:
            query: Query string
            limit: Maximum number of results
            
        Returns:
            List of rule matches
        """
        entries = self.kb.find(query, limit=limit)
        return [RuleMatch(section=e.section, text=e.text) for e in entries]


# Global service instance (would be initialized from config in production)
_service: Optional[RuleKBService] = None


def init_service(knowledge_base: RuleKnowledgeBase):
    """Initialize the service with a knowledge base."""
    global _service
    _service = RuleKBService(knowledge_base)


@app.post("/query", response_model=RuleQueryResponse)
async def query_rules(request: RuleQueryRequest):
    """Query rules endpoint."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    matches = _service.query(request.query, request.limit)
    return RuleQueryResponse(matches=matches)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

