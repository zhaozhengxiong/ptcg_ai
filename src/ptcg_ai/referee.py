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
    requires_selection: bool = False  # 是否需要玩家选择
    candidates: Optional[List[Dict[str, object]]] = None  # 候选列表
    selection_context: Optional[Dict[str, object]] = None  # 选择上下文（操作类型、参数等）


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
            # Ensure payload is a dict, not None
            payload = request.payload if request.payload is not None else {}
            result = handler(request.actor_id, **payload)
        except Exception as exc:  # noqa: BLE001 - we surface user facing errors
            return OperationResult(False, str(exc))
        self.database.persist_state(self.state)
        return OperationResult(True, "ok", data=result)

    def handle_natural_language_request(self, player_id: str, request_text: str, referee_sdk=None) -> OperationResult:
        """处理玩家的自然语言请求。
        
        Args:
            player_id: 提出请求的玩家ID
            request_text: 玩家的自然语言请求
            referee_sdk: RefereeAgentSDK 实例（可选，如果提供则使用其解析能力）
        
        Returns:
            OperationResult 包含执行结果
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[RefereeAgent] handle_natural_language_request 被调用")
        logger.info(f"[RefereeAgent] 玩家ID: {player_id}")
        logger.info(f"[RefereeAgent] 请求文本: {request_text}")
        logger.info(f"[RefereeAgent] referee_sdk 是否提供: {referee_sdk is not None}")
        
        # 如果提供了 referee_sdk，使用它来解析自然语言请求
        if referee_sdk:
            try:
                logger.info(f"[RefereeAgent] 调用 referee_sdk.invoke")
                # 使用 RefereeAgentSDK 解析请求
                invoke_input = {
                    "input": f"玩家 {player_id} 请求: {request_text}",
                    "chat_history": [],
                    "player_id": player_id
                }
                logger.info(f"[RefereeAgent] invoke 输入: {invoke_input}")
                
                result = referee_sdk.invoke(invoke_input)
                logger.info(f"[RefereeAgent] referee_sdk.invoke 返回: {result}")
                
                if result.get("success"):
                    # 检查是否需要玩家选择
                    if result.get("requires_selection"):
                        candidates = result.get("candidates", [])
                        selection_context = result.get("selection_context", {})
                        output = result.get("output", "请选择卡牌")
                        logger.info(f"[RefereeAgent] 需要玩家选择，候选数量: {len(candidates)}")
                        return OperationResult(
                            True,
                            output,
                            requires_selection=True,
                            candidates=candidates,
                            selection_context=selection_context
                        )
                    else:
                        # 从输出中提取操作信息（RefereeAgentSDK 应该已经执行了操作）
                        output = result.get("output", "操作已执行")
                        logger.info(f"[RefereeAgent] 操作成功，返回输出: {output}")
                        return OperationResult(True, output)
                else:
                    error_msg = result.get("error", "解析请求失败")
                    logger.warning(f"[RefereeAgent] 操作失败: {error_msg}")
                    return OperationResult(False, error_msg)
            except Exception as e:
                logger.error(f"[RefereeAgent] 处理自然语言请求时出错: {e}", exc_info=True)
                import traceback
                logger.error(f"[RefereeAgent] 错误堆栈: {traceback.format_exc()}")
                return OperationResult(False, f"处理自然语言请求时出错: {str(e)}")
        else:
            # 如果没有提供 SDK，返回错误提示
            logger.warning(f"[RefereeAgent] 没有提供 referee_sdk")
            return OperationResult(False, "需要 RefereeAgentSDK 来处理自然语言请求")

    def handle_player_selection(self, player_id: str, selection_text: str, selection_context: Dict[str, object], referee_sdk=None) -> OperationResult:
        """处理玩家的选择请求。
        
        Args:
            player_id: 提出选择的玩家ID
            selection_text: 玩家的选择文本（例如："我选择Rotom V(uid:playerA-deck-013)"）
            selection_context: 选择上下文，包含原始操作信息
            referee_sdk: RefereeAgentSDK 实例（可选，用于解析原始请求）
        
        Returns:
            OperationResult 包含执行结果
        """
        import logging
        import re
        logger = logging.getLogger(__name__)
        
        logger.info(f"[RefereeAgent] handle_player_selection 被调用")
        logger.info(f"[RefereeAgent] 玩家ID: {player_id}")
        logger.info(f"[RefereeAgent] 选择文本: {selection_text}")
        logger.info(f"[RefereeAgent] 选择上下文: {selection_context}")
        
        # 从选择文本中提取UID（支持多张卡牌选择）
        uid_pattern = r'uid:([^\s\)]+)'
        uid_matches = re.findall(uid_pattern, selection_text)
        
        if not uid_matches:
            return OperationResult(False, "选择文本中未找到卡牌UID，请使用格式：我选择[卡牌名称](uid:xxxxx) 或 我选择[卡牌1](uid:xxxxx)和[卡牌2](uid:yyyyy)")
        
        # 支持多张卡牌选择（如Battle VIP Pass最多2张，Super Rod最多3张）
        selected_uids = uid_matches
        logger.info(f"[RefereeAgent] 提取的选择UID: {selected_uids} (共{len(selected_uids)}张)")
        
        # 从selection_context中获取原始请求信息
        original_request = selection_context.get("original_request", "")
        tool_name = selection_context.get("tool_name", "")
        tool_args = selection_context.get("tool_args", {})
        
        # 从原始请求中提取训练家卡的UID（如Nest Ball的UID）
        trainer_card_uid = None
        if original_request:
            trainer_uid_matches = re.findall(r'uid:([^\s\)]+)', original_request)
            if trainer_uid_matches:
                trainer_card_uid = trainer_uid_matches[0]  # 第一个UID通常是训练家卡的UID
        
        if not trainer_card_uid:
            return OperationResult(False, "无法从原始请求中提取训练家卡UID")
        
        logger.info(f"[RefereeAgent] 训练家卡UID: {trainer_card_uid}")
        
        # 构建执行操作的payload
        # 对于需要选择的操作，payload应该包含：
        # - card_id: 训练家卡的UID
        # - selected_cards: 玩家选择的卡牌UID列表（支持多张，如Battle VIP Pass最多2张）
        payload = {
            "card_id": trainer_card_uid,
            "selected_cards": selected_uids
        }
        
        # 创建OperationRequest并执行
        request = OperationRequest(
            actor_id=player_id,
            action="play_trainer",
            payload=payload
        )
        
        logger.info(f"[RefereeAgent] 执行选择操作: action=play_trainer, payload={payload}")
        result = self.handle_request(request)
        
        if result.success:
            logger.info(f"[RefereeAgent] 选择操作成功: {result.message}")
            return OperationResult(True, f"选择成功，{result.message}", data=result.data)
        else:
            logger.warning(f"[RefereeAgent] 选择操作失败: {result.message}")
            return OperationResult(False, f"选择操作失败: {result.message}")

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

    def _handle_move_to_bench(self, actor_id: str, card_id: str = None) -> Dict[str, object]:
        """Handle moving a basic Pokémon to bench.
        
        Args:
            actor_id: Player ID
            card_id: UID of the basic Pokémon card in hand (required)
        """
        if not card_id:
            raise ValueError(
                "move_to_bench requires 'card_id' parameter. "
                "Provide the UID of the basic Pokémon card from your hand (check observation hand_cards for the 'uid' field)."
            )
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
    
    def _handle_use_ability(self, actor_id: str, card_id: str = None, ability_name: str = None) -> Dict[str, object]:
        """Handle ability usage request."""
        self._ensure_turn(actor_id)
        
        if not card_id:
            raise ValueError("use_ability requires 'card_id' parameter. Provide the UID of the Pokémon in active or bench.")
        if not ability_name:
            raise ValueError("use_ability requires 'ability_name' parameter. Provide the name of the ability to use.")
        
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
        
        # Check if this is a passive ability (cannot be activated)
        ability_text = str(ability.get("text", "")).lower()
        
        # Passive ability indicators:
        # - "Prevent" (e.g., "Prevent all damage")
        # - "As long as" (e.g., "As long as this Pokémon is in the Active Spot")
        # - "Whenever" (e.g., "Whenever...")
        # - No activation keywords like "Once during your turn", "You may"
        is_passive = (
            "prevent" in ability_text or
            "as long as" in ability_text or
            "whenever" in ability_text or
            ("once during your turn" not in ability_text and "you may" not in ability_text and 
             "search" not in ability_text and "draw" not in ability_text and "discard" not in ability_text)
        )
        
        if is_passive:
            raise ValueError(
                f"Ability '{ability_name}' is a passive ability that is always active. "
                f"It does not need to be activated and cannot be used with 'use_ability'. "
                f"Passive abilities automatically apply their effects (e.g., '{ability.get('text', '')}')."
            )
        
        # Try to load CardExecutionPlan from database
        plan = None
        try:
            from agents.rule_analyst.db_access import load_plan_from_db
            card_id = f"{card.definition.set_code}-{card.definition.number}"
            # 通过 effect_name 加载特定的能力预案
            plan = load_plan_from_db(card_id, effect_name=ability_name, status="approved")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not load plan for ability {ability_name}: {e}")
        
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card,
            referee=self  # 传递 referee 引用以便结束回合
        )
        executor = EffectExecutor(context)
        
        # Use plan if available, otherwise use text-based execution
        if plan and plan.effect_type == "ability" and plan.effect_name == ability_name:
            result = executor.execute_with_plan(plan)
        else:
            result = executor.execute_ability(ability)
        
        return result
    
    def _handle_use_attack(self, actor_id: str, card_id: str = None, attack_name: str = None, target_pokemon_id: Optional[str] = None) -> Dict[str, object]:
        """Handle attack usage request."""
        self._ensure_turn(actor_id)
        
        if not card_id:
            raise ValueError("use_attack requires 'card_id' parameter. Provide the UID of the Pokémon in active spot.")
        if not attack_name:
            raise ValueError("use_attack requires 'attack_name' parameter. Provide the name of the attack to use.")
        
        # Check if first turn of first player (cannot attack)
        if self._is_first_turn_first_player(actor_id):
            raise ValueError("The first player cannot attack on their first turn")
        
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
        
        # Verify energy requirements
        if not self._check_energy_requirements(card, attack):
            raise ValueError(f"Energy requirements not met for attack {attack_name}")
        
        # Try to load CardExecutionPlan from database
        plan = None
        try:
            from agents.rule_analyst.db_access import load_plan_from_db
            card_id = f"{card.definition.set_code}-{card.definition.number}"
            # 通过 effect_name 加载特定的攻击预案
            plan = load_plan_from_db(card_id, effect_name=attack_name, status="approved")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not load plan for attack {attack_name}: {e}")
        
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card,
            referee=self  # 传递 referee 引用以便结束回合
        )
        executor = EffectExecutor(context)
        
        # Use plan if available, otherwise use text-based execution
        if plan and plan.effect_type == "attack" and plan.effect_name == attack_name:
            # For attacks, we need to handle damage separately
            # First execute the plan for non-damage effects
            result = executor.execute_with_plan(plan)
            
            # Then handle damage (if not already handled by plan)
            if "damage" not in result:
                # Fall back to execute_attack for damage calculation
                damage_result = executor.execute_attack(attack, target_pokemon_id)
                result.update(damage_result)
            
            # 处理新的伤害计算模式
            if result.get("damage_to_multiple"):
                # 对多个宝可梦造成伤害
                damage_per = result.get("damage", 0)
                count = result.get("count", 1)
                # 需要选择多个目标（在 RefereeAgent 中处理）
                result["requires_target_selection"] = True
                result["target_count"] = count
                result["damage_per_target"] = damage_per
            elif result.get("attack_does_nothing"):
                # 攻击无效
                result["damage"] = 0
                result["message"] = "Attack does nothing"
        else:
            result = executor.execute_attack(attack, target_pokemon_id)
        
        return result
    
    def _handle_play_trainer(self, actor_id: str, card_id: str = None, target_ids: Optional[List[str]] = None, **kwargs) -> Dict[str, object]:
        """Handle trainer card play request.
        
        Args:
            actor_id: Player ID
            card_id: UID of the trainer card in hand (required)
            target_ids: Optional list of target card UIDs
            **kwargs: Additional parameters (to handle incorrect parameter names)
        """
        self._ensure_turn(actor_id)
        
        # Handle incorrect parameter names (common mistakes)
        if not card_id:
            # Check for common incorrect parameter names
            if "trainer_card" in kwargs:
                raise ValueError(
                    f"Invalid parameter name 'trainer_card'. Use 'card_id' instead. "
                    f"Also, you must use the card's UID (from observation hand_cards), not the card name. "
                    f"Received: {kwargs['trainer_card']}. Please check your hand_cards in the observation and use the 'uid' field."
                )
            elif "card_name" in kwargs:
                raise ValueError(
                    f"Invalid parameter name 'card_name'. Use 'card_id' instead. "
                    f"You must use the card's UID (from observation hand_cards), not the card name. "
                    f"Received: {kwargs['card_name']}. Please check your hand_cards in the observation and use the 'uid' field."
                )
            else:
                raise ValueError(
                    "play_trainer requires 'card_id' parameter. "
                    "Provide the UID of the trainer card from your hand (check observation hand_cards for the 'uid' field). "
                    "Do not use card names, only UIDs."
                )
        
        # Find card in hand
        hand = self.state.players[actor_id].zone(Zone.HAND)
        card = None
        for c in hand.cards:
            if c.uid == card_id:
                card = c
                break
        
        if card is None:
            # Check if they used card name instead of UID
            card_names = [c.definition.name for c in hand.cards]
            if card_id in card_names:
                raise ValueError(
                    f"You used the card name '{card_id}' instead of the UID. "
                    f"Please check your observation hand_cards and use the 'uid' field. "
                    f"Available trainer cards in hand: {[c.definition.name for c in hand.cards if c.definition.card_type == 'Trainer']}"
                )
            else:
                raise ValueError(
                    f"Card with UID '{card_id}' not found in hand. "
                    f"Available trainer cards in hand: {[(c.uid, c.definition.name) for c in hand.cards if c.definition.card_type == 'Trainer']}"
                )
        
        if card.definition.card_type != "Trainer":
            raise ValueError(f"Card {card_id} is not a trainer card")
        
        subtypes = card.definition.subtypes or []
        
        # Check Supporter card restrictions
        if "Supporter" in subtypes:
            # Check if already used a Supporter this turn
            usage_count = self.tools.get_usage_count(actor_id, "supporter", "play_trainer", scope="turn")
            if usage_count > 0:
                raise ValueError("You can only use one Supporter card per turn")
            
            # Check if first turn of first player
            if self._is_first_turn_first_player(actor_id):
                raise ValueError("The first player cannot use Supporter cards on their first turn")
        
        # Check Stadium card restrictions
        if "Stadium" in subtypes:
            # Check if already used a Stadium this turn
            usage_count = self.tools.get_usage_count(actor_id, "stadium", "play_trainer", scope="turn")
            if usage_count > 0:
                raise ValueError("You can only use one Stadium card per turn")
            
            # Check if same Stadium already in play
            stadium_zone = self.state.players[actor_id].zone(Zone.STADIUM)
            for stadium_card in stadium_zone.cards:
                if stadium_card.definition.name == card.definition.name:
                    raise ValueError(f"Stadium card {card.definition.name} is already in play")
        
        # Try to load CardExecutionPlan from database
        plan = None
        try:
            from agents.rule_analyst.db_access import load_plan_from_db
            card_id = f"{card.definition.set_code}-{card.definition.number}"
            plan = load_plan_from_db(card_id, status="approved")
        except Exception as e:
            # If plan loading fails, fall back to text-based execution
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not load plan for {card_id}: {e}")
        
        context = EffectContext(
            game_state=self.state,
            tools=self.tools,
            player_id=actor_id,
            card_instance=card,
            referee=self  # 传递 referee 引用以便结束回合
        )
        executor = EffectExecutor(context)
        
        # Use plan if available, otherwise use text-based execution
        if plan and plan.effect_type == "trainer":
            # Handle selected_cards from kwargs (for cards that require selection)
            selected_cards = kwargs.get("selected_cards") or target_ids
            result = executor.execute_with_plan(plan, selected_cards=selected_cards)
        else:
            # Fall back to text-based execution
            effect_text = card.definition.rules_text or ""
            if not effect_text and card.definition.subtypes:
                effect_text = str(card.definition.rules_text) if card.definition.rules_text else ""
            result = executor.execute_trainer_effect(effect_text)
        
        # Track usage for Supporter and Stadium
        if "Supporter" in subtypes:
            self.tools.track_usage(actor_id, "supporter", "play_trainer", scope="turn")
        elif "Stadium" in subtypes:
            self.tools.track_usage(actor_id, "stadium", "play_trainer", scope="turn")
        
        # Move trainer to discard (unless it's a Stadium)
        if "Stadium" not in subtypes:
            self.tools.move_card(actor_id, Zone.HAND, Zone.DISCARD, card)
        else:
            # For Stadium, move to Stadium zone
            self.tools.move_card(actor_id, Zone.HAND, Zone.STADIUM, card)
        
        return result
    
    def _handle_switch_pokemon(self, actor_id: str, bench_card_id: str = None, opponent: bool = False) -> Dict[str, object]:
        """Handle switching active Pokémon with bench."""
        self._ensure_turn(actor_id)
        
        if not bench_card_id:
            raise ValueError("switch_pokemon requires 'bench_card_id' parameter. Provide the UID of the Pokémon in bench to switch with.")
        
        # Check retreat usage limit (once per turn)
        usage_count = self.tools.get_usage_count(actor_id, "retreat", "switch_pokemon", scope="turn")
        if usage_count > 0:
            raise ValueError("You can only retreat once per turn")
        
        # Find active Pokémon
        active = self.state.players[actor_id].zone(Zone.ACTIVE)
        if not active.cards:
            raise ValueError("No active Pokémon to retreat")
        
        active_pokemon = active.cards[0]
        
        # Check special conditions (Asleep or Paralyzed cannot retreat)
        if "Asleep" in active_pokemon.special_conditions or "Paralyzed" in active_pokemon.special_conditions:
            raise ValueError("Pokémon that are Asleep or Paralyzed cannot retreat")
        
        # Get retreat cost
        retreat_cost = self._get_retreat_cost(active_pokemon)
        
        # Check if enough energy attached
        if len(active_pokemon.attached_energy) < retreat_cost:
            raise ValueError(f"Not enough energy attached. Retreat cost is {retreat_cost}, but only {len(active_pokemon.attached_energy)} energy attached")
        
        # Discard energy cards (retreat cost)
        if retreat_cost > 0:
            energy_to_discard_uids = active_pokemon.attached_energy[:retreat_cost]
            
            # Remove energy from attached list
            for energy_uid in energy_to_discard_uids:
                if energy_uid in active_pokemon.attached_energy:
                    active_pokemon.attached_energy.remove(energy_uid)
            
            # Log the energy discard
            # Note: In a full implementation, we would find the actual energy card instances
            # and move them to discard. For now, we just remove from attached_energy list.
            self.tools.discard(actor_id, [], f"Retreat cost: {retreat_cost} energy discarded")
        
        # Track retreat usage
        self.tools.track_usage(actor_id, "retreat", "switch_pokemon", scope="turn")
        
        # Perform the switch
        self.tools.swap_active_with_bench(actor_id, bench_card_id, opponent)
        return {"success": True, "message": "Pokémon switched"}
    
    def _handle_evolve_pokemon(self, actor_id: str, base_card_id: str = None, evolution_card_id: str = None, skip_stage1: bool = False) -> Dict[str, object]:
        """Handle evolution request.
        
        Args:
            actor_id: Player ID
            base_card_id: UID of the base Pokémon to evolve (required)
            evolution_card_id: UID of the evolution card in hand (required)
            skip_stage1: If True, allows Basic -> Stage 2 evolution (Rare Candy)
        """
        self._ensure_turn(actor_id)
        
        # Validate required parameters
        if not base_card_id:
            raise ValueError("evolve_pokemon requires 'base_card_id' parameter. Provide the UID of the Pokémon in active or bench to evolve.")
        if not evolution_card_id:
            raise ValueError("evolve_pokemon requires 'evolution_card_id' parameter. Provide the UID of the evolution card in your hand.")
        
        # Find base card (in active or bench)
        base_card = None
        active = self.state.players[actor_id].zone(Zone.ACTIVE)
        bench = self.state.players[actor_id].zone(Zone.BENCH)
        
        for card in active.cards:
            if card.uid == base_card_id:
                base_card = card
                break
        
        if base_card is None:
            for card in bench.cards:
                if card.uid == base_card_id:
                    base_card = card
                    break
        
        if base_card is None:
            raise ValueError(f"Base card {base_card_id} not found in active or bench")
        
        # Find evolution card in hand
        hand = self.state.players[actor_id].zone(Zone.HAND)
        evolution_card = None
        for card in hand.cards:
            if card.uid == evolution_card_id:
                evolution_card = card
                break
        
        if evolution_card is None:
            raise ValueError(f"Evolution card {evolution_card_id} not found in hand")
        
        # Check if Pokémon was placed this turn (cannot evolve on first turn in play)
        # Rule: A Pokémon cannot evolve on the turn it was placed, unless using Rare Candy
        player_ids = list(self.state.players.keys())
        is_first_player = actor_id == player_ids[0]
        
        # If it's the first player's first turn, they cannot evolve (unless using Rare Candy)
        if self.state.turn_number == 1 and is_first_player:
            if not skip_stage1:
                raise ValueError("Cannot evolve Pokémon on the first turn of the game. A Pokémon must be in play for at least one turn before evolving (unless using Rare Candy).")
        
        # For other cases, we need to track when the card was placed
        # For now, if it's turn 1 and the card is Basic, it was likely placed this turn
        # TODO: Implement proper placed_turn tracking on CardInstance
        if self.state.turn_number == 1 and base_card.definition.stage == "Basic" and not skip_stage1:
            raise ValueError("Cannot evolve a Pokémon on the turn it was placed. The Pokémon must be in play for at least one turn before evolving (unless using Rare Candy).")
        
        # Check evolution chain
        base_stage = base_card.definition.stage
        evolution_stage = evolution_card.definition.stage
        
        if base_stage == "Basic":
            if evolution_stage == "Stage 1":
                # Valid: Basic -> Stage 1
                pass
            elif evolution_stage == "Stage 2" and skip_stage1:
                # Valid: Basic -> Stage 2 (with Rare Candy)
                pass
            else:
                raise ValueError(f"Invalid evolution: {base_stage} cannot evolve to {evolution_stage}")
        elif base_stage == "Stage 1":
            if evolution_stage == "Stage 2":
                # Valid: Stage 1 -> Stage 2
                pass
            else:
                raise ValueError(f"Invalid evolution: {base_stage} cannot evolve to {evolution_stage}")
        else:
            raise ValueError(f"Cannot evolve from {base_stage}")
        
        # Perform evolution
        self.tools.evolve_pokemon(actor_id, base_card_id, evolution_card_id, skip_stage1)
        return {"success": True, "message": "Pokémon evolved"}
    
    def _handle_attach_energy(self, actor_id: str, energy_card_id: str = None, pokemon_id: str = None) -> Dict[str, object]:
        """Handle energy attachment request.
        
        Args:
            actor_id: Player ID
            energy_card_id: UID of the energy card in hand
            pokemon_id: UID of the target Pokémon (in active or bench)
        """
        self._ensure_turn(actor_id)
        
        if not energy_card_id:
            raise ValueError("attach_energy requires 'energy_card_id' parameter. Provide the UID of the energy card from your hand.")
        if not pokemon_id:
            raise ValueError("attach_energy requires 'pokemon_id' parameter. Provide the UID of the target Pokémon in active or bench.")
        
        # Check if energy already attached this turn (once per turn limit)
        usage_count = self.tools.get_usage_count(actor_id, "energy_attachment", "attach_energy", scope="turn")
        if usage_count > 0:
            raise ValueError("You can only attach one Energy card per turn")
        
        # Attach energy using GameTools
        self.tools.attach_energy(energy_card_id, pokemon_id)
        
        # Track usage
        self.tools.track_usage(actor_id, "energy_attachment", "attach_energy", scope="turn")
        
        return {"success": True, "message": f"Energy attached to Pokémon {pokemon_id}"}

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
    
    def _is_first_turn_first_player(self, player_id: str) -> bool:
        """Check if this is the first turn of the first player.
        
        Args:
            player_id: Player ID to check
            
        Returns:
            True if this is the first player's first turn
        """
        if self.state.turn_number != 1:
            return False
        
        player_ids = list(self.state.players.keys())
        return player_id == player_ids[0]
    
    def _check_energy_requirements(self, pokemon: CardInstance, attack: Dict[str, object]) -> bool:
        """Check if Pokémon has enough energy attached to use the attack.
        
        Args:
            pokemon: The Pokémon card instance
            attack: Attack definition dict with 'cost' key
            
        Returns:
            True if energy requirements are met, False otherwise
        """
        # Get energy cost from attack
        cost = attack.get("cost", [])
        if not cost:
            # No cost means attack is free
            return True
        
        # Count attached energy
        attached_count = len(pokemon.attached_energy)
        
        # For now, we do a simple count check
        # A full implementation would check energy types
        # Cost is typically a list like ["Fire", "Colorless", "Colorless"]
        # where Colorless means any energy type
        if isinstance(cost, list):
            required_count = len(cost)
            return attached_count >= required_count
        elif isinstance(cost, (int, str)):
            # If cost is a number or string representation
            try:
                required_count = int(cost)
                return attached_count >= required_count
            except (ValueError, TypeError):
                # If we can't parse, assume it's met (backward compatibility)
                return True
        
        # Default: assume requirements are met if we can't parse
        return True
    
    def _get_retreat_cost(self, pokemon: CardInstance) -> int:
        """Get retreat cost for a Pokémon.
        
        Args:
            pokemon: The Pokémon card instance
            
        Returns:
            Retreat cost (number of energy to discard)
        """
        # Retreat cost is typically stored in the card definition
        # For now, we'll try to parse from rules_text or use a default
        # A full implementation would add retreat_cost to CardDefinition
        
        # Check if there's a retreat_cost field (future enhancement)
        if hasattr(pokemon.definition, "retreat_cost") and pokemon.definition.retreat_cost is not None:
            return pokemon.definition.retreat_cost
        
        # Try to parse from rules_text (simplified)
        # In PTCG, retreat cost is usually shown as symbols like [C][C] meaning 2 Colorless
        # For now, we'll use a default of 1 if we can't determine
        # This is a simplified implementation - a full version would parse the actual cost
        
        # Default retreat cost: 1 (most common)
        # In a real implementation, this would be parsed from card data
        return 1


__all__ = ["RefereeAgent", "OperationRequest", "OperationResult"]
