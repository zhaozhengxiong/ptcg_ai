"""Admin Console API backend."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional

from src.ptcg_ai.database import DatabaseClient, build_postgres_dsn

app = FastAPI(title="PTCG Admin Console API", version="0.1.0")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class ManualConfirmationRequest(BaseModel):
    """Request for manual confirmation."""
    match_id: str
    decision_id: str
    approved: bool
    notes: Optional[str] = None


class CaseResponse(BaseModel):
    """Case information response."""
    id: str
    match_id: str
    decision_id: str
    approved: bool
    notes: Optional[str]
    created_at: str


def get_db() -> DatabaseClient:
    """Get database client."""
    dsn = build_postgres_dsn()
    return DatabaseClient(dsn=dsn)


@app.post("/confirmations")
async def submit_confirmation(
    request: ManualConfirmationRequest,
    db: DatabaseClient = Depends(get_db),
    # token: str = Depends(verify_token),
):
    """Submit manual confirmation for a referee decision."""
    # TODO: Store confirmation in database
    return {"success": True, "message": "Confirmation submitted"}


@app.get("/cases", response_model=List[CaseResponse])
async def get_cases(
    db: DatabaseClient = Depends(get_db),
    # token: str = Depends(verify_token),
):
    """Get case library."""
    # TODO: Query cases from database
    return []


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}

