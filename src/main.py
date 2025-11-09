from pathlib import Path
from ptcg_ai.simulation import build_deck, load_rulebook_text, run_turn
from ptcg_ai.player import PlayerAgent
from ptcg_ai.referee import RefereeAgent

rulebook = load_rulebook_text(Path("doc/rulebook_extracted.txt"))

deck_a = build_deck("playerA", Path("doc/deck/deck1.txt"))
deck_b = build_deck("playerB", Path("doc/deck/deck1.txt"))

referee = RefereeAgent.create(
    match_id="demo-001",
    player_decks={"playerA": deck_a, "playerB": deck_b},
    knowledge_base=rulebook,
)

players = {"playerA": PlayerAgent("playerA"), "playerB": PlayerAgent("playerB")}
run_turn(referee, players)