"""End-to-end tests for full match simulation."""
import pytest
from pathlib import Path
from src.ptcg_ai.database import DatabaseClient, InMemoryDatabase
from src.ptcg_ai.referee import RefereeAgent
from src.ptcg_ai.player import PlayerAgent
from src.ptcg_ai.rulebook import RuleKnowledgeBase
from src.ptcg_ai.simulation import load_rulebook_text, run_turn
from src.ptcg_ai.models import CardDefinition, CardInstance, Deck


def create_test_deck(owner_id: str, card_count: int = 60) -> Deck:
    """Create a test deck without requiring database connection.
    
    Args:
        owner_id: Owner identifier
        card_count: Number of cards in deck
        
    Returns:
        A valid Deck instance
    """
    card_def = CardDefinition(
        set_code="TEST",
        number="001",
        name="Test Card",
        card_type="Pokemon",
        hp=100,
        stage="Basic",
    )
    
    cards = [
        CardInstance(
            uid=f"{owner_id}-deck-{i+1:03d}",
            owner_id=owner_id,
            definition=card_def,
        )
        for i in range(card_count)
    ]
    
    return Deck(player_id=owner_id, cards=cards)


@pytest.fixture
def rulebook():
    """Load rulebook."""
    rulebook_path = Path("doc/rulebook_extracted.txt")
    if not rulebook_path.exists():
        # Create a minimal rulebook for testing
        return RuleKnowledgeBase.from_text("1 Test rule.")
    return load_rulebook_text(rulebook_path)


@pytest.fixture
def db():
    """Create in-memory database."""
    return DatabaseClient(memory_store=InMemoryDatabase())


def test_match_creation(rulebook, db):
    """Test creating a match."""
    deck_a = create_test_deck("playerA")
    deck_b = create_test_deck("playerB")
    
    referee = RefereeAgent.create(
        match_id="test-match",
        player_decks={"playerA": deck_a, "playerB": deck_b},
        knowledge_base=rulebook,
        database=db,
    )
    
    assert referee.state.match_id == "test-match"
    assert len(referee.state.players) == 2
    assert "playerA" in referee.state.players
    assert "playerB" in referee.state.players


def test_turn_execution(rulebook, db):
    """Test executing a turn."""
    deck_a = create_test_deck("playerA")
    deck_b = create_test_deck("playerB")
    
    referee = RefereeAgent.create(
        match_id="test-match",
        player_decks={"playerA": deck_a, "playerB": deck_b},
        knowledge_base=rulebook,
        database=db,
    )
    
    players = {
        "playerA": PlayerAgent("playerA"),
        "playerB": PlayerAgent("playerB"),
    }
    
    # Run a turn
    run_turn(referee, players)
    
    # Check that logs were created
    logs = db.get_logs("test-match")
    assert len(logs) > 0

