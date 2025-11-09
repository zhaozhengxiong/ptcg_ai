"""FastAPI service for match management, state queries, and replay."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from src.ptcg_ai.database import DatabaseClient, build_postgres_dsn
from src.ptcg_ai.models import GameState, GameLogEntry
from src.ptcg_ai.referee import RefereeAgent
from src.ptcg_ai.simulation import build_deck
from src.ptcg_ai.rulebook import RuleKnowledgeBase

logger = logging.getLogger(__name__)

app = FastAPI(title="PTCG Simulator API", version="0.1.0")

# OAuth2 setup (simplified for now)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Request/Response models
class CreateMatchRequest(BaseModel):
    """Request to create a new match."""
    player_a_deck_file: str
    player_b_deck_file: str
    player_a_id: str = "playerA"
    player_b_id: str = "playerB"


class MatchResponse(BaseModel):
    """Match information response."""
    match_id: str
    turn_player: Optional[str]
    turn_number: int
    phase: str
    players: List[str]


class LogEntryResponse(BaseModel):
    """Log entry response."""
    match_id: str
    actor: str
    action: str
    payload: Dict
    random_seed: Optional[str]
    timestamp: Optional[str]


class ReplayRequest(BaseModel):
    """Request to replay a match."""
    match_id: str
    from_turn: Optional[int] = None
    to_turn: Optional[int] = None


# Global state (in production, use proper state management)
_state_store: Dict[str, GameState] = {}
_referees: Dict[str, RefereeAgent] = {}


def get_db() -> DatabaseClient:
    """Get database client."""
    dsn = build_postgres_dsn()
    return DatabaseClient(dsn=dsn)


def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """Verify OAuth2 token (simplified for now)."""
    # TODO: Implement proper token validation
    return token


@app.post("/matches", response_model=MatchResponse)
async def create_match(
    request: CreateMatchRequest,
    db: DatabaseClient = Depends(get_db),
    # token: str = Depends(verify_token),  # Enable when auth is ready
):
    """Create a new match."""
    try:
        # Load rulebook
        from pathlib import Path
        rulebook_path = Path("doc/rulebook_extracted.txt")
        if not rulebook_path.exists():
            raise HTTPException(status_code=500, detail="Rulebook not found")
        
        rulebook = RuleKnowledgeBase.from_text(rulebook_path.read_text())
        
        # Build decks
        deck_a = build_deck(request.player_a_id, request.player_a_deck_file)
        deck_b = build_deck(request.player_b_id, request.player_b_deck_file)
        
        # Create referee and match
        referee = RefereeAgent.create(
            match_id=f"match-{len(_state_store) + 1}",
            player_decks={
                request.player_a_id: deck_a,
                request.player_b_id: deck_b,
            },
            knowledge_base=rulebook,
            database=db,
        )
        
        match_id = referee.state.match_id
        _state_store[match_id] = referee.state
        _referees[match_id] = referee
        
        return MatchResponse(
            match_id=match_id,
            turn_player=referee.state.turn_player,
            turn_number=referee.state.turn_number,
            phase=referee.state.phase,
            players=list(referee.state.players.keys()),
        )
    except Exception as e:
        logger.error(f"创建对局时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/matches/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: str,
    # token: str = Depends(verify_token),
):
    """Get match state."""
    if match_id not in _state_store:
        raise HTTPException(status_code=404, detail="Match not found")
    
    state = _state_store[match_id]
    return MatchResponse(
        match_id=match_id,
        turn_player=state.turn_player,
        turn_number=state.turn_number,
        phase=state.phase,
        players=list(state.players.keys()),
    )


@app.get("/matches/{match_id}/logs", response_model=List[LogEntryResponse])
async def get_match_logs(
    match_id: str,
    db: DatabaseClient = Depends(get_db),
    # token: str = Depends(verify_token),
):
    """Get match logs."""
    try:
        logs = db.get_logs(match_id)
        return [
            LogEntryResponse(
                match_id=log.match_id,
                actor=log.actor,
                action=log.action,
                payload=log.payload,
                random_seed=log.random_seed.hex() if log.random_seed else None,
                timestamp=None,  # TODO: Add timestamp to GameLogEntry
            )
            for log in logs
        ]
    except Exception as e:
        logger.error(f"获取日志时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/matches/{match_id}/replay")
async def replay_match(
    match_id: str,
    request: ReplayRequest,
    db: DatabaseClient = Depends(get_db),
    # token: str = Depends(verify_token),
):
    """Replay a match from logs."""
    try:
        logs = db.get_logs(match_id)
        
        # Filter by turn range if specified
        if request.from_turn or request.to_turn:
            # TODO: Filter logs by turn number
            pass
        
        # Replay logic would go here
        # For now, just return the logs
        return {
            "match_id": match_id,
            "logs_count": len(logs),
            "message": "Replay functionality to be implemented",
        }
    except Exception as e:
        logger.error(f"重放对局时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

