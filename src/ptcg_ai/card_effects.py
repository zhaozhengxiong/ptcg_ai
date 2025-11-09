"""Card effect parsing and execution framework for deck1 support."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Any

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
    referee: Optional[Any] = None  # Optional RefereeAgent reference for ending turns


class EffectExecutor:
    """Executes card effects by parsing text and calling appropriate tools."""
    
    def __init__(self, context: EffectContext):
        self.context = context
    
    def execute_with_plan(self, plan: Any, selected_cards: Optional[List[str]] = None) -> Dict[str, object]:
        """Execute card effect using a CardExecutionPlan.
        
        Args:
            plan: CardExecutionPlan object from rule_analyst
            selected_cards: Optional list of selected card UIDs (if selection was already made)
            
        Returns:
            Result dict with execution status. May include requires_selection=True if player selection is needed.
        """
        from agents.rule_analyst.analyzer import CardExecutionPlan
        
        if not isinstance(plan, CardExecutionPlan):
            return {"success": False, "message": "Invalid plan type"}
        
        # Execute validation rules
        for validation in plan.validation_rules:
            validation_result = self._execute_validation(validation)
            if not validation_result.get("valid", True):
                return {
                    "success": False,
                    "message": validation_result.get("error_message", "Validation failed")
                }
        
        # Execute execution steps
        result = {"success": True, "message": "Effect executed"}
        executed_steps = []
        
        for step_idx, step in enumerate(plan.execution_steps):
            # Check dependencies
            depends_on = step.get("depends_on", [])
            if depends_on:
                for dep_idx in depends_on:
                    if dep_idx >= len(executed_steps):
                        return {"success": False, "message": f"Step {step_idx} depends on step {dep_idx} which hasn't been executed"}
            
            # Check if step should be skipped
            skip_if = step.get("skip_if")
            if skip_if:
                # Simple skip conditions (can be extended)
                if skip_if == "no_stadium":
                    stadium = self.context.tools.check_stadium_in_play(self.context.player_id)
                    if not stadium:
                        continue
            
            # Execute step
            step_result = self._execute_step(step, selected_cards, executed_steps)
            
            if not step_result.get("success", True):
                return step_result
            
            # Check if step requires player selection
            if step_result.get("requires_selection"):
                return {
                    "success": True,
                    "requires_selection": True,
                    "candidates": step_result.get("candidates", []),
                    "selection_context": {
                        "plan": plan,
                        "step_index": step_idx,
                        "executed_steps": executed_steps
                    },
                    "message": step_result.get("message", "Please select cards")
                }
            
            executed_steps.append(step_result)
            result.update(step_result)
        
        return result
    
    def _execute_validation(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a validation rule."""
        validation_type = validation.get("type")
        
        if validation_type == "in_active":
            active = self.context.game_state.players[self.context.player_id].zone(Zone.ACTIVE)
            if self.context.card_instance not in active.cards:
                return {"valid": False, "error_message": validation.get("error_message", "Card must be in active spot")}
        
        elif validation_type == "energy_requirement":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "bench_full":
            if self.context.tools.check_bench_full(self.context.player_id):
                return {"valid": False, "error_message": validation.get("error_message", "Bench is full")}
        
        elif validation_type == "ability_used":
            ability_name = validation.get("params", {}).get("ability_name", "")
            usage_count = self.context.tools.get_usage_count(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="turn"
            )
            if usage_count > 0:
                return {"valid": False, "error_message": validation.get("error_message", f"Ability {ability_name} already used this turn")}
        
        elif validation_type == "ability_used_game":
            ability_name = validation.get("params", {}).get("ability_name", "")
            usage_count = self.context.tools.get_usage_count(
                self.context.player_id,
                self.context.card_instance.uid,
                "ability",
                scope="game"
            )
            if usage_count > 0:
                return {"valid": False, "error_message": validation.get("error_message", f"Ability {ability_name} already used this game")}
        
        elif validation_type == "in_hand":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "supporter_used":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "first_turn_restriction":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "stadium_used":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "stadium_duplicate":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "tool_attached":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        elif validation_type == "energy_attachment_limit":
            # This is checked by RefereeAgent before calling EffectExecutor
            pass
        
        return {"valid": True}
    
    def _execute_step(self, step: Dict[str, Any], selected_cards: Optional[List[str]], executed_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a single execution step."""
        step_type = step.get("step_type")
        action = step.get("action")
        params = step.get("params", {})
        
        if step_type == "validation":
            # Validations are handled separately
            return {"success": True}
        
        elif step_type == "query":
            if action == "query_deck_candidates":
                # This should return candidates for selection
                criteria = params
                candidates = self._query_deck_by_criteria(criteria)
                return {
                    "success": True,
                    "requires_selection": True,
                    "candidates": [{"uid": c.uid, "name": c.definition.name} for c in candidates],
                    "message": f"Found {len(candidates)} candidates"
                }
            
            elif action == "query_discard_candidates":
                criteria = params
                candidates = self._query_discard_by_criteria(criteria)
                return {
                    "success": True,
                    "requires_selection": True,
                    "candidates": [{"uid": c.uid, "name": c.definition.name} for c in candidates],
                    "message": f"Found {len(candidates)} candidates"
                }
            
            elif action == "query_opponent_bench":
                bench_cards = self.context.tools.query_opponent_bench(self.context.player_id)
                return {
                    "success": True,
                    "requires_selection": True,
                    "candidates": [{"uid": c.uid, "name": c.definition.name} for c in bench_cards],
                    "message": f"Found {len(bench_cards)} opponent bench Pokémon"
                }
            
            elif action == "reveal_top_cards":
                count = params.get("count", 1)
                revealed = self.context.tools.reveal_top(self.context.player_id, count)
                return {
                    "success": True,
                    "revealed": [c.uid for c in revealed],
                    "revealed_cards": revealed
                }
        
        elif step_type == "selection":
            if selected_cards:
                # Selection was already made
                return {"success": True, "selected": selected_cards}
            else:
                # Need to wait for selection
                max_count = params.get("max_count", 1)
                min_count = params.get("min_count", 0)
                # Get candidates from previous query step
                candidates = []
                for prev_step in executed_steps:
                    if "candidates" in prev_step:
                        candidates = prev_step["candidates"]
                        break
                
                return {
                    "success": True,
                    "requires_selection": True,
                    "candidates": candidates,
                    "max_count": max_count,
                    "min_count": min_count,
                    "message": f"Please select {min_count} to {max_count} card(s)"
                }
        
        elif step_type == "move":
            if action == "move_cards":
                if not selected_cards:
                    return {"success": False, "message": "No cards selected"}
                
                source = params.get("source")
                target = params.get("target")
                
                # Map target string to Zone
                target_zone_map = {
                    "hand": Zone.HAND,
                    "bench": Zone.BENCH,
                    "discard": Zone.DISCARD,
                    "lost_zone": Zone.LOST_ZONE
                }
                target_zone = target_zone_map.get(target)
                
                if not target_zone:
                    return {"success": False, "message": f"Unknown target zone: {target}"}
                
                # Find and move cards
                moved_count = 0
                for card_uid in selected_cards:
                    card = self._find_card(card_uid, source)
                    if card:
                        source_zone_map = {
                            "deck": Zone.DECK,
                            "discard": Zone.DISCARD,
                            "hand": Zone.HAND
                        }
                        source_zone = source_zone_map.get(source)
                        if source_zone:
                            self.context.tools.move_card(self.context.player_id, source_zone, target_zone, card)
                            moved_count += 1
                
                return {"success": True, "moved": moved_count, "message": f"Moved {moved_count} card(s) to {target}"}
            
            elif action == "attach_energy":
                if not selected_cards:
                    return {"success": False, "message": "No energy card selected"}
                # Energy attachment is handled by RefereeAgent
                return {"success": True, "message": "Energy attachment ready"}
            
            elif action == "discard_stadium":
                stadium = self.context.tools.check_stadium_in_play(self.context.player_id)
                if stadium:
                    self.context.tools.discard_stadium(self.context.player_id)
                    return {"success": True, "message": "Stadium discarded"}
                return {"success": True, "message": "No stadium to discard"}
            
            elif action == "switch_opponent_pokemon":
                if not selected_cards:
                    return {"success": False, "message": "No Pokémon selected"}
                bench_card_id = selected_cards[0]
                self.context.tools.swap_active_with_bench(self.context.player_id, bench_card_id, opponent=True)
                return {"success": True, "message": "Opponent Pokémon switched"}
        
        elif step_type == "shuffle":
            if action == "shuffle_deck":
                self.context.tools.shuffle(self.context.player_id, Zone.DECK)
                return {"success": True, "message": "Deck shuffled"}
        
        elif step_type == "draw":
            if action == "draw_cards":
                count = params.get("count", 1)
                drawn = self.context.tools.draw(self.context.player_id, count)
                return {"success": True, "drawn": [c.uid for c in drawn], "message": f"Drew {len(drawn)} card(s)"}
            
            elif action == "draw_cards_by_prizes":
                prize_count = self.context.tools.query_prize_count(self.context.player_id)
                drawn = self.context.tools.draw(self.context.player_id, prize_count)
                return {"success": True, "drawn": [c.uid for c in drawn], "message": f"Drew {len(drawn)} card(s) based on prizes"}
        
        elif step_type == "damage":
            if action == "calculate_and_apply_damage":
                base_damage = params.get("base_damage", 0)
                modifiers = params.get("damage_modifiers", [])
                damage_calc = params.get("damage_calculation")  # 新的伤害计算信息
                
                total_damage = base_damage
                for modifier in modifiers:
                    if modifier.get("type") == "prize_based":
                        opponent_id = [p for p in self.context.game_state.players.keys() if p != self.context.player_id][0]
                        prize_count = self.context.tools.query_opponent_prize_count(self.context.player_id)
                        bonus = modifier.get("bonus_per_prize", 0) * prize_count
                        total_damage += bonus
                    elif modifier.get("type") == "bonus_per":
                        # 新的伤害计算模式：每X增加N点伤害
                        condition = modifier.get("condition", "")
                        bonus = modifier.get("bonus", 0)
                        # 根据条件计算奖励（需要根据具体条件实现）
                        # 例如：如果是 "Prize card your opponent has taken"，查询对手奖赏卡
                        if "prize" in condition.lower() and "opponent" in condition.lower():
                            prize_count = self.context.tools.query_opponent_prize_count(self.context.player_id)
                            total_damage += bonus * prize_count
                        # 可以添加更多条件处理
                    elif modifier.get("type") == "bonus":
                        # 新的伤害计算模式：增加N点伤害
                        bonus = modifier.get("bonus", 0)
                        total_damage += bonus
                    elif modifier.get("type") == "self_damage":
                        self_damage = modifier.get("amount", 0)
                        self.context.tools.update_damage(self.context.card_instance.uid, self_damage)
                        self.context.tools.check_ko(self.context.card_instance.uid)
                    elif modifier.get("type") == "damage_to_multiple":
                        # 新的伤害计算模式：对多个宝可梦造成伤害
                        # 这个需要在 RefereeAgent 中处理，因为需要选择目标
                        damage_per = modifier.get("damage", 0)
                        count = modifier.get("count", 1)
                        return {
                            "success": True,
                            "damage": damage_per,
                            "damage_to_multiple": True,
                            "count": count,
                            "message": f"Damage {damage_per} to {count} opponent Pokémon"
                        }
                    elif modifier.get("type") == "attack_does_nothing":
                        # 新的伤害计算模式：攻击无效
                        return {
                            "success": True,
                            "damage": 0,
                            "attack_does_nothing": True,
                            "message": "Attack does nothing"
                        }
                
                # Damage to target is handled by RefereeAgent
                return {"success": True, "damage": total_damage, "message": f"Damage calculated: {total_damage}"}
        
        elif step_type == "attach":
            if action == "attach_energy_cards":
                if not selected_cards:
                    # 如果没有选择能量卡，且步骤是可选的，则跳过
                    if params.get("optional", False):
                        return {"success": True, "skipped": True, "message": "No energy cards selected (optional step)"}
                    return {"success": False, "message": "No energy cards selected"}
                
                allow_multiple_targets = params.get("allow_multiple_targets", False)
                
                if allow_multiple_targets:
                    # 需要为每张能量卡选择目标宝可梦
                    # 返回一个需要多次选择的结果
                    return {
                        "success": True,
                        "requires_selection": True,
                        "selection_type": "attach_energy",
                        "energy_cards": selected_cards,
                        "allow_multiple_targets": True,
                        "message": f"Please select target Pokémon for each of {len(selected_cards)} energy card(s)"
                    }
                else:
                    # 所有能量卡附着到同一个目标（需要选择目标）
                    return {
                        "success": True,
                        "requires_selection": True,
                        "selection_type": "attach_energy",
                        "energy_cards": selected_cards,
                        "allow_multiple_targets": False,
                        "message": f"Please select target Pokémon for {len(selected_cards)} energy card(s)"
                    }
        
        elif step_type == "check":
            if action == "check_stadium_in_play":
                stadium = self.context.tools.check_stadium_in_play(self.context.player_id)
                return {"success": True, "stadium_exists": stadium is not None}
        
        elif step_type == "end_turn":
            if action == "end_turn":
                if self.context.referee:
                    result = self.context.referee.end_turn(self.context.player_id)
                    return {"success": True, "turn_ended": True, **result}
                else:
                    # 如果没有 referee 引用，返回标记让调用者处理
                    return {"success": True, "turn_ended": True, "message": "Turn should end (no referee reference)"}
        
        elif step_type == "heal":
            if action == "heal_damage":
                amount = params.get("amount", "all")
                target = params.get("target", "this Pokémon")
                # 调用 GameTools 的 heal_damage 方法（如果存在）
                if hasattr(self.context.tools, "heal_damage"):
                    result = self.context.tools.heal_damage(self.context.player_id, self.context.card_instance.uid, amount, target)
                    return {"success": True, "healed": amount, "message": f"Healed {amount} damage from {target}"}
                else:
                    # 如果方法不存在，返回标记让调用者处理
                    return {"success": True, "healed": amount, "message": f"Heal {amount} damage from {target} (method not implemented)"}
        
        elif step_type == "move_damage_counters":
            if action == "move_damage_counters":
                count = params.get("count", "all")
                source = params.get("source", "")
                target = params.get("target", "")
                # 调用 GameTools 的 move_damage_counters 方法（如果存在）
                if hasattr(self.context.tools, "move_damage_counters"):
                    result = self.context.tools.move_damage_counters(self.context.player_id, source, target, count)
                    return {"success": True, "moved": count, "message": f"Moved {count} damage counters from {source} to {target}"}
                else:
                    # 如果方法不存在，返回标记让调用者处理
                    return {"success": True, "moved": count, "message": f"Move {count} damage counters from {source} to {target} (method not implemented)"}
        
        elif step_type == "move_energy":
            if action == "move_energy":
                count = params.get("count", 1)
                energy_type = params.get("energy_type")
                source = params.get("source", "")
                target = params.get("target", "")
                # 调用 GameTools 的 move_energy 方法（如果存在）
                if hasattr(self.context.tools, "move_energy"):
                    result = self.context.tools.move_energy(self.context.player_id, source, target, count, energy_type)
                    return {"success": True, "moved": count, "message": f"Moved {count} energy from {source} to {target}"}
                else:
                    # 如果方法不存在，返回标记让调用者处理
                    return {"success": True, "moved": count, "message": f"Move {count} energy from {source} to {target} (method not implemented)"}
        
        elif step_type == "devolve":
            if action == "devolve_pokemon":
                target = params.get("target", "")
                method = params.get("method", "")
                # 调用 GameTools 的 devolve_pokemon 方法（如果存在）
                if hasattr(self.context.tools, "devolve_pokemon"):
                    result = self.context.tools.devolve_pokemon(self.context.player_id, target, method)
                    return {"success": True, "devolved": True, "message": f"Devolved {target}"}
                else:
                    # 如果方法不存在，返回标记让调用者处理
                    return {"success": True, "devolved": True, "message": f"Devolve {target} (method not implemented)"}
        
        return {"success": True, "message": "Step executed"}
    
    def _query_deck_by_criteria(self, criteria: Dict[str, Any]) -> List[CardInstance]:
        """Query deck using criteria from plan."""
        def predicate(card: CardInstance) -> bool:
            if criteria.get("card_type"):
                if card.definition.card_type != criteria["card_type"]:
                    return False
            if criteria.get("stage"):
                if card.definition.stage != criteria["stage"]:
                    return False
            if criteria.get("max_hp") is not None:
                if card.definition.card_type != "Pokemon" or card.definition.hp is None:
                    return False
                if card.definition.hp > criteria["max_hp"]:
                    return False
            if criteria.get("energy_type"):
                if card.definition.card_type != "Energy":
                    return False
                if criteria["energy_type"] == "Basic Energy":
                    if "Basic" not in (card.definition.subtypes or []):
                        return False
            if criteria.get("subtype"):
                if card.definition.card_type != "Trainer":
                    return False
                if criteria["subtype"] not in (card.definition.subtypes or []):
                    return False
            return True
        
        return self.context.tools.deck_query(self.context.player_id, predicate)
    
    def _query_discard_by_criteria(self, criteria: Dict[str, Any]) -> List[CardInstance]:
        """Query discard pile using criteria from plan."""
        def predicate(card: CardInstance) -> bool:
            if criteria.get("card_type"):
                if card.definition.card_type != criteria["card_type"]:
                    return False
            if criteria.get("stage"):
                if card.definition.stage != criteria["stage"]:
                    return False
            if criteria.get("energy_type"):
                if card.definition.card_type != "Energy":
                    return False
                if criteria["energy_type"] == "Basic Energy":
                    if "Basic" not in (card.definition.subtypes or []):
                        return False
            return True
        
        return self.context.tools.query_discard(self.context.player_id, predicate)
    
    def _find_card(self, card_uid: str, source: str) -> Optional[CardInstance]:
        """Find a card by UID in the specified source zone."""
        source_zone_map = {
            "deck": Zone.DECK,
            "discard": Zone.DISCARD,
            "hand": Zone.HAND
        }
        source_zone = source_zone_map.get(source)
        if not source_zone:
            return None
        
        zone_state = self.context.game_state.players[self.context.player_id].zone(source_zone)
        for card in zone_state.cards:
            if card.uid == card_uid:
                return card
        return None
    
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

