"""Implementation of the referee agent orchestrating the match."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .card_effects import EffectContext, EffectExecutor
from .database import DatabaseClient
from .game_tools import GameTools, ToolCallContext
from .models import CardInstance, Deck, GameState, PlayerState, Zone
from .rulebook import RuleKnowledgeBase


@dataclass
class OperationRequest:
    """Structured request emitted by a player agent."""

    actor_id: str
    action: str
    payload: Dict[str, object]


@dataclass
class OperationResult:
    success: bool
    message: str
    data: Optional[Dict[str, object]] = None


@dataclass
class RefereeAgent:
    """High level orchestrator that enforces rules before calling tools."""

    referee_id: str
    knowledge_base: RuleKnowledgeBase
    database: DatabaseClient
    state: GameState
    tools: GameTools = field(init=False)

    def __post_init__(self) -> None:
        self.tools = GameTools(
            context=ToolCallContext(
                match_id=self.state.match_id,
                referee_id=self.referee_id,
                db=self.database,
            ),
            state=self.state,
        )

    # ------------------------------------------------------------------
    # match setup
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, match_id: str, player_decks: Dict[str, Deck], knowledge_base: RuleKnowledgeBase, database: Optional[DatabaseClient] = None) -> "RefereeAgent":
        for deck in player_decks.values():
            deck.validate()
        players = {
            player_id: PlayerState(player_id=player_id)
            for player_id in player_decks
        }
        state = GameState(match_id=match_id, players=players)
        db = database or DatabaseClient()
        referee = cls(
            referee_id="referee",
            knowledge_base=knowledge_base,
            database=db,
            state=state,
        )
        referee._initialise_decks(player_decks)
        return referee

    def _initialise_decks(self, player_decks: Dict[str, Deck]) -> None:
        for player_id, deck in player_decks.items():
            zone = self.state.players[player_id].zone(Zone.DECK)
            zone.cards[:] = list(deck.cards)
            self.tools.shuffle(player_id, Zone.DECK)
            prize_zone = self.state.players[player_id].zone(Zone.PRIZE)
            prize_zone.cards[:] = zone.cards[:6]
            del zone.cards[:6]
            self.database.persist_state(self.state)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def handle_request(self, request: OperationRequest) -> OperationResult:
        handler_name = f"_handle_{request.action}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            return OperationResult(False, f"Unknown action: {request.action}")
        try:
            result = handler(request.actor_id, **request.payload)
        except Exception as exc:  # noqa: BLE001 - we surface user facing errors
            return OperationResult(False, str(exc))
        self.database.persist_state(self.state)
        return OperationResult(True, "ok", data=result)

    # ------------------------------------------------------------------
    # handlers
    # ------------------------------------------------------------------
    def _handle_draw(self, actor_id: str, count: int) -> Dict[str, object]:
        self._ensure_turn(actor_id)
        cards = self.tools.draw(actor_id, count)
        return {"cards": [card.uid for card in cards]}

    def _handle_discard(self, actor_id: str, card_ids: Iterable[str], reason: str) -> Dict[str, object]:
        cards = self._locate_cards(actor_id, Zone.HAND, card_ids)
        self.tools.discard(actor_id, cards, reason)
        return {"discarded": list(card_ids)}

    def _handle_take_prize(self, actor_id: str, count: int = 1) -> Dict[str, object]:
        cards = self.tools.take_prize(actor_id, count)
        return {"cards": [card.uid for card in cards], "remaining": self.state.players[actor_id].prizes_remaining}

    def _handle_move_to_bench(self, actor_id: str, card_id: str) -> Dict[str, object]:
        card = self._locate_cards(actor_id, Zone.HAND, [card_id])[0]
        self.tools.move_card(actor_id, Zone.HAND, Zone.BENCH, card)
        return {"bench": [c.uid for c in self.state.players[actor_id].zone(Zone.BENCH).cards]}

    def _handle_query_rule(self, actor_id: str, query: str, limit: int = 3) -> Dict[str, object]:
        _ = actor_id  # For future access control checks
        matches = self.knowledge_base.find(query, limit=limit)
        return {
            "matches": [
                {
                    "section": entry.section,
                    "text": entry.text,
                }
                for entry in matches
            ]
        }
    
    def _handle_use_ability(self, actor_id: str, card_id: str, ability_name: str) -> Dict[str, object]:
        """Handle ability usage request."""
        self._ensure_turn(actor_id)
        
        # Find card
        card = None
        for zone in [Zone.ACTIVE, Zone.BENCH]:
            zone_state = self.state.players[actor_id].zone(zone)
            for c in zone_state.cards:
                if c.uid == card_id:
                    card = c
                    break
            if card:
                break
        
        if card is None:
            raise ValueError(f"Card {card_id} not found in active or bench")
        
        # Find ability
        if not card.definition.abilities:
            raise ValueError(f"Card {card_id} has no abilities")
        
        ability = None
        for ab in card.definition.abilities:
            if ab.get("name") == ability_name:
                ability = ab
                break
        
        if ability is None:
            raise ValueError(f"Ability {ability_name} not found on card {card_id}")
        
        # Execute ability
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card
        )
        executor = EffectExecutor(context)
        result = executor.execute_ability(ability)
        
        return result
    
    def _handle_use_attack(self, actor_id: str, card_id: str, attack_name: str, target_pokemon_id: Optional[str] = None) -> Dict[str, object]:
        """Handle attack usage request."""
        self._ensure_turn(actor_id)
        
        # Find attacking card
        active = self.state.players[actor_id].zone(Zone.ACTIVE)
        card = None
        for c in active.cards:
            if c.uid == card_id:
                card = c
                break
        
        if card is None:
            raise ValueError(f"Card {card_id} not found in active spot")
        
        # Find attack
        if not card.definition.attacks:
            raise ValueError(f"Card {card_id} has no attacks")
        
        attack = None
        for atk in card.definition.attacks:
            if atk.get("name") == attack_name:
                attack = atk
                break
        
        if attack is None:
            raise ValueError(f"Attack {attack_name} not found on card {card_id}")
        
        # Execute attack
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card
        )
        executor = EffectExecutor(context)
        result = executor.execute_attack(attack, target_pokemon_id)
        
        return result
    
    def _handle_play_trainer(self, actor_id: str, card_id: str, target_ids: Optional[List[str]] = None) -> Dict[str, object]:
        """Handle trainer card play request."""
        self._ensure_turn(actor_id)
        
        # Find card in hand
        hand = self.state.players[actor_id].zone(Zone.HAND)
        card = None
        for c in hand.cards:
            if c.uid == card_id:
                card = c
                break
        
        if card is None:
            raise ValueError(f"Card {card_id} not found in hand")
        
        if card.definition.card_type != "Trainer":
            raise ValueError(f"Card {card_id} is not a trainer card")
        
        # Execute trainer effect
        effect_text = card.definition.rules_text or ""
        if not effect_text and card.definition.subtypes:
            # Try to get effect from first rule
            effect_text = str(card.definition.rules_text) if card.definition.rules_text else ""
        
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card
        )
        executor = EffectExecutor(context)
        result = executor.execute_trainer_effect(effect_text)
        
        # Move trainer to discard (unless it's a Stadium)
        if "Stadium" not in (card.definition.subtypes or []):
            self.tools.move_card(actor_id, Zone.HAND, Zone.DISCARD, card)
        
        return result
    
    def _handle_switch_pokemon(self, actor_id: str, bench_card_id: str, opponent: bool = False) -> Dict[str, object]:
        """Handle switching active Pokémon with bench."""
        self._ensure_turn(actor_id)
        self.tools.swap_active_with_bench(actor_id, bench_card_id, opponent)
        return {"success": True, "message": "Pokémon switched"}
    
    def _handle_evolve_pokemon(self, actor_id: str, base_card_id: str, evolution_card_id: str, skip_stage1: bool = False) -> Dict[str, object]:
        """Handle evolution request."""
        self._ensure_turn(actor_id)
        self.tools.evolve_pokemon(actor_id, base_card_id, evolution_card_id, skip_stage1)
        return {"success": True, "message": "Pokémon evolved"}

    # ------------------------------------------------------------------
    # helper functions
    # ------------------------------------------------------------------
    def _ensure_turn(self, actor_id: str) -> None:
        """Ensure it's the requesting player's turn."""
        if self.state.turn_player is None:
            # First action - determine starting player
            self._determine_starting_player()
        if self.state.turn_player != actor_id:
            raise RuntimeError(f"It is not {actor_id}'s turn (current turn: {self.state.turn_player})")
    
    def _determine_starting_player(self) -> None:
        """Determine starting player (coin flip simulation)."""
        # Simple: use first player in players dict
        # In a real game, this would be determined by coin flip
        player_ids = list(self.state.players.keys())
        self.state.turn_player = player_ids[0]
        self.state.turn_number = 1
        self.state.phase = "draw"
    
    def start_turn(self, player_id: str) -> Dict[str, object]:
        """Start a new turn for a player.
        
        This should be called at the beginning of each turn.
        """
        if self.state.turn_player is None:
            self._determine_starting_player()
        
        if self.state.turn_player != player_id:
            raise RuntimeError(f"Cannot start turn for {player_id} (current turn: {self.state.turn_player})")
        
        # Draw card at start of turn
        drawn = self.tools.draw(player_id, 1)
        
        # Reset turn-scoped usage trackers
        self.state.players[player_id].reset_turn_usage()
        
        # Set phase to main
        self.state.phase = "main"
        
        return {
            "success": True,
            "message": f"Turn {self.state.turn_number} started for {player_id}",
            "drawn": [c.uid for c in drawn] if drawn else []
        }
    
    def end_turn(self, player_id: str) -> Dict[str, object]:
        """End current turn and switch to next player."""
        if self.state.turn_player != player_id:
            raise RuntimeError(f"Cannot end turn for {player_id} (current turn: {self.state.turn_player})")
        
        # Switch to next player
        player_ids = list(self.state.players.keys())
        current_index = player_ids.index(player_id)
        next_index = (current_index + 1) % len(player_ids)
        next_player = player_ids[next_index]
        
        self.state.turn_player = next_player
        if next_index == 0:  # Wrapped around - new round
            self.state.turn_number += 1
        
        self.state.phase = "draw"
        
        return {
            "success": True,
            "message": f"Turn ended, switching to {next_player}",
            "next_player": next_player,
            "turn_number": self.state.turn_number
        }
    
    def check_win_condition(self) -> Optional[str]:
        """Check if any player has won.
        
        Returns:
            Player ID of winner, or None if game continues
        """
        for player_id, player_state in self.state.players.items():
            # Check prize cards
            if player_state.prizes_remaining <= 0:
                return player_id
            
            # Check deck empty (simplified - would need to check if can draw)
            deck = player_state.zone(Zone.DECK)
            if len(deck.cards) == 0:
                # Opponent wins
                opponent_id = [p for p in self.state.players.keys() if p != player_id][0]
                return opponent_id
            
            # Check no active Pokémon (simplified)
            active = player_state.zone(Zone.ACTIVE)
            if len(active.cards) == 0:
                # Check if bench has Pokémon
                bench = player_state.zone(Zone.BENCH)
                if len(bench.cards) == 0:
                    # Opponent wins
                    opponent_id = [p for p in self.state.players.keys() if p != player_id][0]
                    return opponent_id
        
        return None

    def _locate_cards(self, player_id: str, zone: Zone, card_ids: Iterable[str]) -> List[CardInstance]:
        zone_state = self.state.players[player_id].zone(zone)
        lookup = {card.uid: card for card in zone_state.cards}
        try:
            return [lookup[card_id] for card_id in card_ids]
        except KeyError as exc:
            raise ValueError(f"Card {exc.args[0]} not present in {zone.value}") from exc


__all__ = ["RefereeAgent", "OperationRequest", "OperationResult"]
