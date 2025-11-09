"""Integration tests for Game Tools service."""
import pytest
from src.ptcg_ai.database import DatabaseClient, InMemoryDatabase
from src.ptcg_ai.models import CardDefinition, CardInstance, GameState, PlayerState, Zone


@pytest.fixture
def game_state():
    """Create a test game state."""
    players = {
        "playerA": PlayerState(player_id="playerA"),
        "playerB": PlayerState(player_id="playerB"),
    }
    return GameState(match_id="test-match", players=players)


@pytest.fixture
def db():
    """Create in-memory database."""
    return DatabaseClient(memory_store=InMemoryDatabase())


def test_game_tools_draw(game_state, db):
    """Test drawing cards."""
    from src.ptcg_ai.game_tools import GameTools, ToolCallContext
    
    # Add cards to deck
    card_def = CardDefinition(
        set_code="TEST",
        number="001",
        name="Test Card",
        card_type="Pokemon",
        hp=100,
    )
    for i in range(5):
        card = CardInstance(
            uid=f"test-card-{i}",
            owner_id="playerA",
            definition=card_def,
        )
        game_state.players["playerA"].zone(Zone.DECK).cards.append(card)
    
    tools = GameTools(
        context=ToolCallContext(
            match_id="test-match",
            referee_id="referee",
            db=db,
        ),
        state=game_state,
    )
    
    # Draw 3 cards
    drawn = tools.draw("playerA", 3)
    
    assert len(drawn) == 3
    assert len(game_state.players["playerA"].zone(Zone.DECK).cards) == 2
    assert len(game_state.players["playerA"].zone(Zone.HAND).cards) == 3


def test_game_tools_shuffle(game_state, db):
    """Test shuffling deck."""
    from src.ptcg_ai.game_tools import GameTools, ToolCallContext
    
    # Add cards to deck
    card_def = CardDefinition(
        set_code="TEST",
        number="001",
        name="Test Card",
        card_type="Pokemon",
    )
    cards = [
        CardInstance(uid=f"card-{i}", owner_id="playerA", definition=card_def)
        for i in range(10)
    ]
    game_state.players["playerA"].zone(Zone.DECK).cards = cards
    
    original_order = [c.uid for c in cards]
    
    tools = GameTools(
        context=ToolCallContext(
            match_id="test-match",
            referee_id="referee",
            db=db,
        ),
        state=game_state,
    )
    
    tools.shuffle("playerA", Zone.DECK)
    
    new_order = [c.uid for c in game_state.players["playerA"].zone(Zone.DECK).cards]
    
    # Order should be different (very unlikely to be the same)
    assert new_order != original_order
    # But same cards
    assert set(new_order) == set(original_order)

