"""Card effect parsing and execution framework for deck1 support."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .game_tools import GameTools
from .models import CardInstance, GameState, Zone


@dataclass
class EffectContext:
    """Context for executing card effects."""
    
    game_state: GameState
    tools: GameTools
    player_id: str
    card_instance: CardInstance
    target_player_id: Optional[str] = None  # For opponent effects


class EffectExecutor:
    """Executes card effects by parsing text and calling appropriate tools."""
    
    def __init__(self, context: EffectContext):
        self.context = context
    
    def execute_ability(self, ability: Dict[str, object]) -> Dict[str, object]:
        """Execute a Pokémon ability.
        
        Args:
            ability: Ability dict with 'name' and 'text' keys
            
        Returns:
            Result dict with execution status
        """
        ability_text = str(ability.get("text", ""))
        ability_name = str(ability.get("name", ""))
        
        # Check usage restrictions
        if "Once during your turn" in ability_text:
            usage_count = self.context.tools.get_usage_count(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="turn"
            )
            if usage_count > 0:
                return {"success": False, "message": f"{ability_name} already used this turn"}
        
        if "Once during your game" in ability_text or "Once per game" in ability_text:
            usage_count = self.context.tools.get_usage_count(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="game"
            )
            if usage_count > 0:
                return {"success": False, "message": f"{ability_name} already used this game"}
        
        # Check conditions
        if "if this Pokémon is in the Active Spot" in ability_text:
            active = self.context.game_state.players[self.context.player_id].zone(Zone.ACTIVE)
            if self.context.card_instance not in active.cards:
                return {"success": False, "message": f"{ability_name} requires this Pokémon to be Active"}
        
        # Execute based on ability text patterns
        result = self._execute_effect_text(ability_text)
        
        # Track usage
        if "Once during your turn" in ability_text:
            self.context.tools.track_usage(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="turn"
            )
        elif "Once during your game" in ability_text or "Once per game" in ability_text:
            self.context.tools.track_usage(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="game"
            )
        
        return result
    
    def execute_attack(self, attack: Dict[str, object], target_pokemon_id: Optional[str] = None) -> Dict[str, object]:
        """Execute a Pokémon attack.
        
        Args:
            attack: Attack dict with 'name', 'cost', 'damage', 'text' keys
            target_pokemon_id: Optional target Pokémon UID
            
        Returns:
            Result dict with execution status and damage dealt
        """
        attack_text = str(attack.get("text", ""))
        attack_name = str(attack.get("name", ""))
        base_damage = self._parse_damage(attack.get("damage", ""))
        
        # Verify energy cost (simplified - full implementation would check attached energy)
        # For now, we assume energy requirements are met
        
        # Calculate total damage (base + modifiers from text)
        total_damage = base_damage or 0
        
        # Parse damage modifiers from attack text
        if target_pokemon_id:
            # Check for prize-based damage (e.g., Charizard ex "Burning Darkness")
            if "for each prize card" in attack_text.lower() or "for each prize" in attack_text.lower():
                match = re.search(r"(\d+)\s+more damage", attack_text.lower())
                if match:
                    bonus_per_prize = int(match.group(1))
                    # Get opponent's prize count
                    opponent_id = [p for p in self.context.game_state.players.keys() if p != self.context.player_id][0]
                    prize_count = self.context.tools.query_prize_count(opponent_id)
                    total_damage += bonus_per_prize * prize_count
            
            # Check for self-damage (e.g., Charmander OBF 26 "Heat Tackle")
            if "does" in attack_text.lower() and "damage to itself" in attack_text.lower():
                match = re.search(r"does (\d+) damage to itself", attack_text.lower())
                if match:
                    self_damage = int(match.group(1))
                    # Apply self-damage to attacker
                    self.context.tools.update_damage(self.context.card_instance.uid, self_damage)
                    self.context.tools.check_ko(self.context.card_instance.uid)
        
        # Execute attack effects (non-damage effects)
        result = self._execute_effect_text(attack_text)
        
        # Apply damage to target
        if total_damage > 0 and target_pokemon_id:
            # Apply damage
            self.context.tools.update_damage(target_pokemon_id, total_damage)
            
            # Check for KO
            is_ko = self.context.tools.check_ko(target_pokemon_id)
            
            result["damage_dealt"] = total_damage
            result["ko"] = is_ko
        
        return result
    
    def execute_trainer_effect(self, effect_text: str) -> Dict[str, object]:
        """Execute a trainer card effect.
        
        Args:
            effect_text: Effect text from card rules
            
        Returns:
            Result dict with execution status
        """
        return self._execute_effect_text(effect_text)
    
    def _execute_effect_text(self, text: str) -> Dict[str, object]:
        """Execute effect text by pattern matching common effects."""
        text_lower = text.lower()
        
        # Search deck patterns
        if "search your deck" in text_lower:
            return self._handle_search_deck(text)
        
        # Reveal top patterns
        if "look at the top" in text_lower or "reveal the top" in text_lower:
            return self._handle_reveal_top(text)
        
        # Discard patterns
        if "discard" in text_lower and "from your hand" in text_lower:
            return self._handle_discard_from_hand(text)
        
        # Shuffle patterns
        if "shuffle" in text_lower:
            return self._handle_shuffle(text)
        
        # Switch patterns
        if "switch" in text_lower:
            return self._handle_switch(text)
        
        # Draw patterns
        if "draw" in text_lower:
            return self._handle_draw(text)
        
        # Evolution patterns
        if "evolve" in text_lower:
            return self._handle_evolve(text)
        
        # Default: effect executed but no specific action
        return {"success": True, "message": "Effect executed"}
    
    def _handle_search_deck(self, text: str) -> Dict[str, object]:
        """Handle 'search your deck' effects."""
        # Extract search criteria
        max_count = 1
        if "up to" in text.lower():
            match = re.search(r"up to (\d+)", text.lower())
            if match:
                max_count = int(match.group(1))
        
        # Determine filter
        predicate = None
        if "basic pokémon" in text.lower() or "basic pokemon" in text.lower():
            predicate = lambda c: (
                c.definition.card_type == "Pokemon" and
                c.definition.stage == "Basic"
            )
        elif "pokémon" in text.lower() or "pokemon" in text.lower():
            if "hp" in text.lower() and "or less" in text.lower():
                # Level Ball: HP <= 90
                match = re.search(r"(\d+)\s+hp", text.lower())
                if match:
                    max_hp = int(match.group(1))
                    predicate = lambda c: (
                        c.definition.card_type == "Pokemon" and
                        c.definition.hp is not None and
                        c.definition.hp <= max_hp
                    )
            else:
                predicate = lambda c: c.definition.card_type == "Pokemon"
        elif "energy" in text.lower():
            if "basic energy" in text.lower():
                predicate = lambda c: (
                    c.definition.card_type == "Energy" and
                    "Basic" in (c.definition.subtypes or [])
                )
            else:
                predicate = lambda c: c.definition.card_type == "Energy"
        elif "item" in text.lower():
            predicate = lambda c: (
                c.definition.card_type == "Trainer" and
                "Item" in (c.definition.subtypes or [])
            )
        elif "tool" in text.lower():
            predicate = lambda c: (
                c.definition.card_type == "Trainer" and
                "Tool" in (c.definition.subtypes or [])
            )
        
        # Execute search
        candidates = self.context.tools.deck_query(self.context.player_id, predicate) if predicate else []
        selected = self.context.tools.select_from_candidates(candidates, max_count)
        
        # Determine destination
        if "onto your bench" in text.lower() or "put them onto your bench" in text.lower():
            for card in selected:
                self.context.tools.move_card(
                    self.context.player_id,
                    Zone.DECK,
                    Zone.BENCH,
                    card
                )
        elif "into your hand" in text.lower() or "put it into your hand" in text.lower():
            for card in selected:
                self.context.tools.move_card(
                    self.context.player_id,
                    Zone.DECK,
                    Zone.HAND,
                    card
                )
        
        # Shuffle if mentioned
        if "shuffle" in text.lower():
            self.context.tools.shuffle(self.context.player_id, Zone.DECK)
        
        return {
            "success": True,
            "message": f"Searched deck and selected {len(selected)} card(s)",
            "selected": [c.uid for c in selected]
        }
    
    def _handle_reveal_top(self, text: str) -> Dict[str, object]:
        """Handle 'reveal top X cards' effects."""
        match = re.search(r"top (\d+)", text.lower())
        if match:
            count = int(match.group(1))
            revealed = self.context.tools.reveal_top(self.context.player_id, count)
            
            # Check for selection (e.g., Mew's Mysterious Tail)
            if "reveal" in text.lower() and "put it into your hand" in text.lower():
                # Find matching card type
                filter_type = None
                if "item" in text.lower():
                    filter_type = lambda c: (
                        c.definition.card_type == "Trainer" and
                        "Item" in (c.definition.subtypes or [])
                    )
                
                if filter_type:
                    matching = [c for c in revealed if filter_type(c)]
                    if matching:
                        selected = matching[0]
                        self.context.tools.move_card(
                            self.context.player_id,
                            Zone.DECK,
                            Zone.HAND,
                            selected
                        )
                        # Shuffle rest back
                        for card in revealed:
                            if card != selected:
                                # Cards are already in deck, just shuffle
                                pass
                        self.context.tools.shuffle(self.context.player_id, Zone.DECK)
                        return {
                            "success": True,
                            "message": f"Revealed top {count} cards, selected {selected.definition.name}",
                            "selected": selected.uid
                        }
            
            return {
                "success": True,
                "message": f"Revealed top {count} cards",
                "revealed": [c.uid for c in revealed]
            }
        
        return {"success": False, "message": "Could not parse reveal count"}
    
    def _handle_discard_from_hand(self, text: str) -> Dict[str, object]:
        """Handle discard from hand effects."""
        # This is typically handled by the caller providing card IDs
        # For now, return success
        return {"success": True, "message": "Discard effect ready"}
    
    def _handle_shuffle(self, text: str) -> Dict[str, object]:
        """Handle shuffle effects."""
        if "hand" in text.lower() and "into your deck" in text.lower():
            self.context.tools.shuffle_hand_into_deck(self.context.player_id)
            return {"success": True, "message": "Shuffled hand into deck"}
        elif "deck" in text.lower():
            self.context.tools.shuffle(self.context.player_id, Zone.DECK)
            return {"success": True, "message": "Shuffled deck"}
        
        return {"success": True, "message": "Shuffle effect executed"}
    
    def _handle_switch(self, text: str) -> Dict[str, object]:
        """Handle switch effects."""
        # This requires target card ID from caller
        return {"success": True, "message": "Switch effect ready (requires target)"}
    
    def _handle_draw(self, text: str) -> Dict[str, object]:
        """Handle draw effects."""
        # Extract count
        match = re.search(r"draw (\d+)", text.lower())
        if match:
            count = int(match.group(1))
        elif "for each" in text.lower():
            # Dynamic count based on prizes (Iono)
            prize_count = self.context.tools.query_prize_count(self.context.player_id)
            count = prize_count
        else:
            count = 1
        
        drawn = self.context.tools.draw(self.context.player_id, count)
        return {
            "success": True,
            "message": f"Drew {len(drawn)} card(s)",
            "drawn": [c.uid for c in drawn]
        }
    
    def _handle_evolve(self, text: str) -> Dict[str, object]:
        """Handle evolution effects."""
        # This requires base and evolution card IDs from caller
        return {"success": True, "message": "Evolution effect ready (requires cards)"}
    
    def _parse_damage(self, damage_str: str) -> Optional[int]:
        """Parse damage string to integer."""
        if not damage_str or damage_str == "":
            return None
        try:
            return int(damage_str)
        except (ValueError, TypeError):
            return None


__all__ = ["EffectContext", "EffectExecutor"]

