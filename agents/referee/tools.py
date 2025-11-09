"""LangChain tools for Referee Agent."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.ptcg_ai.referee import OperationRequest, RefereeAgent
from src.ptcg_ai.models import Zone

logger = logging.getLogger(__name__)


class ValidateActionInput(BaseModel):
    """Input schema for validate_action tool."""

    action: str = Field(description="行动类型（draw, discard, attack 等）")
    player_id: str = Field(description="执行行动的玩家ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动特定的参数")


class QueryRuleInput(BaseModel):
    """Input schema for query_rule tool."""

    query: str = Field(description="在规则中搜索的查询字符串")
    limit: int = Field(default=5, description="最大结果数量")


class GetCardInfoInput(BaseModel):
    """Input schema for get_card_info tool."""

    card_uid: str = Field(description="卡牌的UID")
    player_id: str = Field(description="玩家ID")


class GetGameStateInput(BaseModel):
    """Input schema for get_game_state tool."""

    player_id: str = Field(description="玩家ID（获取该玩家的游戏状态）")
    include_opponent: bool = Field(default=True, description="是否包含对手信息")


class QueryDeckCandidatesInput(BaseModel):
    """Input schema for query_deck_candidates tool."""

    player_id: str = Field(description="玩家ID")
    card_type: Optional[str] = Field(default=None, description="卡牌类型（Pokemon, Trainer, Energy）")
    stage: Optional[str] = Field(default=None, description="宝可梦阶段（Basic, Stage1, Stage2）")
    max_hp: Optional[int] = Field(default=None, description="最大HP（用于Level Ball等）")
    energy_type: Optional[str] = Field(default=None, description="能量类型（Basic Energy等）")
    limit: int = Field(default=50, description="最大返回数量")


class QueryDiscardCandidatesInput(BaseModel):
    """Input schema for query_discard_candidates tool."""

    player_id: str = Field(description="玩家ID")
    card_type: Optional[str] = Field(default=None, description="卡牌类型（Pokemon, Trainer, Energy）")
    stage: Optional[str] = Field(default=None, description="宝可梦阶段（Basic, Stage1, Stage2）")
    energy_type: Optional[str] = Field(default=None, description="能量类型（Basic Energy等）")
    limit: int = Field(default=50, description="最大返回数量")


class CheckRulesInput(BaseModel):
    """Input schema for check_rules tool."""

    action: str = Field(description="操作类型（use_attack, play_trainer等）")
    player_id: str = Field(description="玩家ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="操作参数")


class ExecuteActionInput(BaseModel):
    """Input schema for execute_action tool."""

    action: str = Field(description="要执行的行动")
    player_id: str = Field(description="玩家ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动参数")


class ParsePlayerRequestInput(BaseModel):
    """Input schema for parse_player_request tool."""

    request_text: str = Field(description="玩家的自然语言请求")
    player_id: str = Field(description="提出请求的玩家ID")


def create_referee_tools(base_referee: RefereeAgent) -> list[StructuredTool]:
    """Create LangChain tools for the referee agent.

    Args:
        base_referee: Base RefereeAgent instance

    Returns:
        List of StructuredTool instances
    """
    def validate_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """根据游戏规则验证玩家行动。"""
        logger.info(f"[Referee] validate_action 被调用: action={action}, player_id={player_id}, payload={payload}")
        request = OperationRequest(
            actor_id=player_id,
            action=action,
            payload=payload,
        )
        result = base_referee.handle_request(request)
        response = {"valid": result.success, "message": result.message}
        logger.info(f"[Referee] validate_action 返回: {response}")
        return json.dumps(response)

    def query_rule(query: str, limit: int = 5) -> str:
        """在规则知识库中查询相关规则。"""
        logger.info(f"[Referee] query_rule 被调用: query={query}, limit={limit}")
        matches = base_referee.knowledge_base.find(query, limit=limit)
        results = [{"section": m.section, "text": m.text} for m in matches]
        logger.info(f"[Referee] query_rule 返回 {len(results)} 条规则")
        return json.dumps(results, ensure_ascii=False)

    def get_card_info(card_uid: str, player_id: str) -> str:
        """根据卡牌UID获取卡牌的详细信息，包括rules_text、abilities、attacks等。
        
        这个工具可以帮助你理解卡牌的效果，从而更好地解析玩家的请求。
        
        Args:
            card_uid: 卡牌的UID（格式：playerA-deck-xxx）
            player_id: 玩家ID
        
        Returns:
            JSON字符串，包含卡牌的详细信息
        """
        logger.info(f"[Referee] get_card_info 被调用: card_uid={card_uid}, player_id={player_id}")
        
        state = base_referee.state
        player_state = state.players.get(player_id)
        
        if not player_state:
            error = {"error": True, "message": f"玩家 {player_id} 不存在"}
            logger.warning(f"[Referee] get_card_info 错误: {error}")
            return json.dumps(error, ensure_ascii=False)
        
        # 在所有区域中查找卡牌
        card = None
        zone_name = None
        for zone in [Zone.HAND, Zone.ACTIVE, Zone.BENCH, Zone.DECK, Zone.DISCARD, Zone.PRIZE]:
            zone_state = player_state.zone(zone)
            for c in zone_state.cards:
                if c.uid == card_uid:
                    card = c
                    zone_name = zone.value
                    break
            if card:
                break
        
        if not card:
            error = {"error": True, "message": f"卡牌 {card_uid} 未找到"}
            logger.warning(f"[Referee] get_card_info 错误: {error}")
            return json.dumps(error, ensure_ascii=False)
        
        # 构建卡牌信息
        card_info = {
            "uid": card.uid,
            "name": card.definition.name,
            "type": card.definition.card_type,
            "stage": card.definition.stage,
            "hp": card.definition.hp,
            "current_hp": card.hp if hasattr(card, 'hp') else None,
            "damage": card.damage if hasattr(card, 'damage') else None,
            "subtypes": card.definition.subtypes or [],
            "rules_text": card.definition.rules_text or "",
            "abilities": card.definition.abilities or [],
            "attacks": card.definition.attacks or [],
            "zone": zone_name,
            "attached_energy_count": len(card.attached_energy) if hasattr(card, 'attached_energy') else 0,
        }
        
        logger.info(f"[Referee] get_card_info 返回: {card_info['name']} ({card_info['type']})")
        logger.info(f"[Referee] get_card_info - rules_text: {card_info['rules_text'][:100] if card_info['rules_text'] else 'None'}...")
        logger.info(f"[Referee] get_card_info - abilities: {len(card_info['abilities'])} 个")
        logger.info(f"[Referee] get_card_info - attacks: {len(card_info['attacks'])} 个")
        
        return json.dumps(card_info, ensure_ascii=False, default=str)

    def get_game_state(player_id: str, include_opponent: bool = True) -> str:
        """获取玩家的完整游戏状态信息，包括手牌、战斗区、备战区、牌库、弃牌区、奖赏卡等。
        
        这个工具可以帮助你理解当前游戏状态，从而更好地判断玩家请求的合法性。
        
        Args:
            player_id: 玩家ID
            include_opponent: 是否包含对手信息（默认True）
        
        Returns:
            JSON字符串，包含完整的游戏状态信息
        """
        logger.info(f"[Referee] get_game_state 被调用: player_id={player_id}, include_opponent={include_opponent}")
        
        state = base_referee.state
        player_state = state.players.get(player_id)
        
        if not player_state:
            error = {"error": True, "message": f"玩家 {player_id} 不存在"}
            logger.warning(f"[Referee] get_game_state 错误: {error}")
            return json.dumps(error, ensure_ascii=False)
        
        # 获取玩家自己的状态
        hand = player_state.zone(Zone.HAND)
        active = player_state.zone(Zone.ACTIVE)
        bench = player_state.zone(Zone.BENCH)
        deck = player_state.zone(Zone.DECK)
        discard = player_state.zone(Zone.DISCARD)
        prize = player_state.zone(Zone.PRIZE)
        
        game_state = {
            "player_id": player_id,
            "turn_number": state.turn_number,
            "phase": state.phase.value if hasattr(state.phase, 'value') else str(state.phase),
            "current_turn_player": state.turn_player,
            "my_state": {
                "hand_size": len(hand.cards),
                "hand_cards": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "type": card.definition.card_type,
                        "stage": card.definition.stage,
                        "hp": card.definition.hp,
                        "subtypes": card.definition.subtypes or [],
                        "rules_text": card.definition.rules_text or "",
                        "abilities": card.definition.abilities or [],
                        "attacks": card.definition.attacks or [],
                    }
                    for card in hand.cards
                ],
                "active_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "abilities": card.definition.abilities or [],
                        "attacks": card.definition.attacks or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in active.cards
                ],
                "bench_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "abilities": card.definition.abilities or [],
                        "attacks": card.definition.attacks or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in bench.cards
                ],
                "deck_size": len(deck.cards),
                "discard_size": len(discard.cards),
                "discard_pile": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "type": card.definition.card_type,
                    }
                    for card in discard.cards[-10:]  # 只显示最近10张
                ],
                "prizes_remaining": player_state.prizes_remaining,
                "prize_count": len(prize.cards),
            }
        }
        
        # 获取对手状态（如果请求）
        if include_opponent:
            opponent_id = None
            for pid in state.players.keys():
                if pid != player_id:
                    opponent_id = pid
                    break
            
            if opponent_id:
                opponent_state = state.players[opponent_id]
                opponent_hand = opponent_state.zone(Zone.HAND)
                opponent_active = opponent_state.zone(Zone.ACTIVE)
                opponent_bench = opponent_state.zone(Zone.BENCH)
                opponent_discard = opponent_state.zone(Zone.DISCARD)
                
                game_state["opponent_state"] = {
                    "player_id": opponent_id,
                    "hand_size": len(opponent_hand.cards),
                    "active_pokemon": [
                        {
                            "uid": card.uid,
                            "name": card.definition.name,
                            "hp": card.hp,
                            "max_hp": card.definition.hp,
                            "damage": card.damage,
                            "attached_energy_count": len(card.attached_energy),
                            "abilities": card.definition.abilities or [],
                            "attacks": card.definition.attacks or [],
                            "special_conditions": card.special_conditions or [],
                        }
                        for card in opponent_active.cards
                    ],
                    "bench_pokemon": [
                        {
                            "uid": card.uid,
                            "name": card.definition.name,
                            "hp": card.hp,
                            "max_hp": card.definition.hp,
                            "damage": card.damage,
                            "attached_energy_count": len(card.attached_energy),
                            "abilities": card.definition.abilities or [],
                            "attacks": card.definition.attacks or [],
                            "special_conditions": card.special_conditions or [],
                        }
                        for card in opponent_bench.cards
                    ],
                    "deck_size": len(opponent_state.zone(Zone.DECK).cards),
                    "discard_size": len(opponent_discard.cards),
                    "discard_pile": [
                        {
                            "uid": card.uid,
                            "name": card.definition.name,
                            "type": card.definition.card_type,
                        }
                        for card in opponent_discard.cards[-10:]  # 只显示最近10张
                    ],
                    "prizes_remaining": opponent_state.prizes_remaining,
                }
        
        logger.info(f"[Referee] get_game_state 返回:")
        logger.info(f"[Referee]   - 手牌: {len(hand.cards)} 张")
        logger.info(f"[Referee]   - 战斗区: {len(active.cards)} 张")
        logger.info(f"[Referee]   - 备战区: {len(bench.cards)} 张")
        logger.info(f"[Referee]   - 牌库: {len(deck.cards)} 张")
        logger.info(f"[Referee]   - 奖赏卡: {player_state.prizes_remaining} 张")
        if include_opponent and "opponent_state" in game_state:
            logger.info(f"[Referee]   - 对手手牌: {game_state['opponent_state']['hand_size']} 张")
        
        return json.dumps(game_state, ensure_ascii=False, default=str)

    def query_deck_candidates(
        player_id: str,
        card_type: Optional[str] = None,
        stage: Optional[str] = None,
        max_hp: Optional[int] = None,
        energy_type: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """查询牌库中符合条件的候选卡牌，返回候选列表但不执行移动操作。
        
        这个工具用于需要玩家选择的操作（如Nest Ball搜索基础宝可梦），
        返回候选列表供玩家选择。
        
        Args:
            player_id: 玩家ID
            card_type: 卡牌类型（Pokemon, Trainer, Energy）
            stage: 宝可梦阶段（Basic, Stage1, Stage2）
            max_hp: 最大HP（用于Level Ball等）
            energy_type: 能量类型（Basic Energy等）
            limit: 最大返回数量
        
        Returns:
            JSON字符串，包含候选卡牌列表
        """
        logger.info(f"[Referee] query_deck_candidates 被调用: player_id={player_id}, card_type={card_type}, stage={stage}, max_hp={max_hp}, limit={limit}")
        
        state = base_referee.state
        player_state = state.players.get(player_id)
        
        if not player_state:
            error = {"error": True, "message": f"玩家 {player_id} 不存在"}
            logger.warning(f"[Referee] query_deck_candidates 错误: {error}")
            return json.dumps(error, ensure_ascii=False)
        
        deck = player_state.zone(Zone.DECK)
        candidates = []
        
        for card in deck.cards[:limit]:
            # 应用过滤条件
            if card_type and card.definition.card_type != card_type:
                continue
            if stage and card.definition.stage != stage:
                continue
            if max_hp is not None:
                if card.definition.card_type != "Pokemon" or card.definition.hp is None:
                    continue
                if card.definition.hp > max_hp:
                    continue
            if energy_type:
                if card.definition.card_type != "Energy":
                    continue
                if energy_type == "Basic Energy":
                    if not card.definition.subtypes or "Basic" not in card.definition.subtypes:
                        continue
            
            # 构建候选卡牌信息
            card_info = {
                "uid": card.uid,
                "name": card.definition.name,
                "type": card.definition.card_type,
                "stage": card.definition.stage,
                "hp": card.definition.hp,
                "subtypes": card.definition.subtypes or [],
            }
            candidates.append(card_info)
        
        result = {
            "candidates": candidates,
            "count": len(candidates),
            "total_deck_size": len(deck.cards)
        }
        
        logger.info(f"[Referee] query_deck_candidates 返回: {len(candidates)} 张候选卡牌")
        return json.dumps(result, ensure_ascii=False, default=str)

    def query_discard_candidates(
        player_id: str,
        card_type: Optional[str] = None,
        stage: Optional[str] = None,
        energy_type: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """查询弃牌堆中符合条件的候选卡牌，返回候选列表但不执行移动操作。
        
        这个工具用于需要玩家选择的操作（如Super Rod从弃牌堆选择卡牌），
        返回候选列表供玩家选择。
        
        Args:
            player_id: 玩家ID
            card_type: 卡牌类型（Pokemon, Trainer, Energy）
            stage: 宝可梦阶段（Basic, Stage1, Stage2）
            energy_type: 能量类型（Basic Energy等）
            limit: 最大返回数量
        
        Returns:
            JSON字符串，包含候选卡牌列表
        """
        logger.info(f"[Referee] query_discard_candidates 被调用: player_id={player_id}, card_type={card_type}, stage={stage}, limit={limit}")
        
        state = base_referee.state
        player_state = state.players.get(player_id)
        
        if not player_state:
            error = {"error": True, "message": f"玩家 {player_id} 不存在"}
            logger.warning(f"[Referee] query_discard_candidates 错误: {error}")
            return json.dumps(error, ensure_ascii=False)
        
        discard = player_state.zone(Zone.DISCARD)
        candidates = []
        
        for card in discard.cards[:limit]:
            # 应用过滤条件
            if card_type and card.definition.card_type != card_type:
                continue
            if stage and card.definition.stage != stage:
                continue
            if energy_type:
                if card.definition.card_type != "Energy":
                    continue
                if energy_type == "Basic Energy":
                    if not card.definition.subtypes or "Basic" not in card.definition.subtypes:
                        continue
            
            # 构建候选卡牌信息
            card_info = {
                "uid": card.uid,
                "name": card.definition.name,
                "type": card.definition.card_type,
                "stage": card.definition.stage,
                "hp": card.definition.hp,
                "subtypes": card.definition.subtypes or [],
            }
            candidates.append(card_info)
        
        result = {
            "candidates": candidates,
            "count": len(candidates),
            "total_discard_size": len(discard.cards)
        }
        
        logger.info(f"[Referee] query_discard_candidates 返回: {len(candidates)} 张候选卡牌")
        return json.dumps(result, ensure_ascii=False, default=str)

    def check_rules(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """检查操作是否符合关键游戏规则，但不执行操作。
        
        这个工具用于在解析请求后、执行操作前检查关键规则，特别是：
        - 先手玩家第一回合不能攻击
        - 先手玩家第一回合不能使用Supporter卡
        - 其他回合限制规则
        
        Args:
            action: 操作类型（use_attack, play_trainer等）
            player_id: 玩家ID
            payload: 操作参数
        
        Returns:
            JSON字符串，包含检查结果
        """
        logger.info(f"[Referee] check_rules 被调用: action={action}, player_id={player_id}, payload={payload}")
        
        state = base_referee.state
        turn_number = state.turn_number
        player_ids = list(state.players.keys())
        is_first_player = player_id == player_ids[0] if player_ids else False
        
        violations = []
        
        # 检查：先手玩家第一回合不能攻击
        if action == "use_attack":
            if turn_number == 1 and is_first_player:
                violation_msg = "先手玩家第一回合不能攻击。这是游戏规则，请等待下一个回合再攻击。"
                violations.append(violation_msg)
                logger.warning(f"[Referee] 规则违反: {violation_msg}")
        
        # 检查：先手玩家第一回合不能使用Supporter卡
        if action == "play_trainer":
            card_id = payload.get("card_id")
            if card_id:
                # 查找卡牌信息
                player_state = state.players.get(player_id)
                if player_state:
                    hand = player_state.zone(Zone.HAND)
                    card = None
                    for c in hand.cards:
                        if c.uid == card_id:
                            card = c
                            break
                    
                    if card and card.definition.subtypes:
                        if "Supporter" in card.definition.subtypes:
                            if turn_number == 1 and is_first_player:
                                violation_msg = f"先手玩家第一回合不能使用Supporter卡（{card.definition.name}）。这是游戏规则，请等待下一个回合再使用。"
                                violations.append(violation_msg)
                                logger.warning(f"[Referee] 规则违反: {violation_msg}")
        
        if violations:
            result = {
                "valid": False,
                "violations": violations,
                "message": "; ".join(violations)
            }
            logger.info(f"[Referee] check_rules 返回: 发现 {len(violations)} 个规则违反")
            return json.dumps(result, ensure_ascii=False)
        else:
            result = {
                "valid": True,
                "message": "关键规则检查通过"
            }
            logger.info(f"[Referee] check_rules 返回: 规则检查通过")
            return json.dumps(result, ensure_ascii=False)

    def execute_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """使用游戏工具执行已验证的行动。"""
        logger.info(f"[Referee] execute_action 被调用")
        logger.info(f"[Referee] 操作类型: {action}")
        logger.info(f"[Referee] 玩家ID: {player_id}")
        logger.info(f"[Referee] 参数: {payload}")
        
        request = OperationRequest(
            actor_id=player_id,
            action=action,
            payload=payload,
        )
        logger.info(f"[Referee] 创建 OperationRequest: actor_id={request.actor_id}, action={request.action}, payload={request.payload}")
        
        result = base_referee.handle_request(request)
        logger.info(f"[Referee] handle_request 返回: success={result.success}, message={result.message}")
        
        if result.success:
            response = {
                "success": True, 
                "message": result.message or "操作成功",
                "data": result.data
            }
            logger.info(f"[Referee] 操作成功: {response}")
            return json.dumps(response, ensure_ascii=False)
        else:
            response = {
                "success": False,
                "message": result.message or "操作失败",
                "error": result.message
            }
            logger.warning(f"[Referee] 操作失败: {response}")
            return json.dumps(response, ensure_ascii=False)

    validate_action_tool = StructuredTool.from_function(
        func=validate_action,
        name="validate_action",
        description="根据游戏规则验证玩家行动。返回包含成功状态和消息的验证结果。注意：这个工具会实际执行操作来验证，如果需要只检查规则不执行，请使用check_rules工具。",
        args_schema=ValidateActionInput,
    )

    check_rules_tool = StructuredTool.from_function(
        func=check_rules,
        name="check_rules",
        description="""检查操作是否符合关键游戏规则，但不执行操作。
        
        **⚠️ 重要：在解析请求后、执行操作前，必须使用此工具检查关键规则！**
        
        这个工具专门用于检查关键规则，特别是：
        - 先手玩家第一回合不能攻击
        - 先手玩家第一回合不能使用Supporter卡
        - 其他回合限制规则
        
        使用场景：
        - 解析请求后，立即调用此工具检查关键规则
        - 如果返回valid=False，必须立即拒绝操作，不要继续执行
        - 如果返回valid=True，可以继续执行操作
        
        示例：
        - 如果操作是use_attack且turn_number=1且玩家是先手玩家，此工具会返回valid=False
        - 如果操作是play_trainer且是Supporter卡且turn_number=1且玩家是先手玩家，此工具会返回valid=False
        """,
        args_schema=CheckRulesInput,
    )

    query_rule_tool = StructuredTool.from_function(
        func=query_rule,
        name="query_rule",
        description="在规则知识库中查询相关规则。返回匹配的规则章节和文本。在处理复杂请求时，应该先查询相关规则来理解操作是否合法。",
        args_schema=QueryRuleInput,
    )

    get_card_info_tool = StructuredTool.from_function(
        func=get_card_info,
        name="get_card_info",
        description="""根据卡牌UID获取卡牌的详细信息，包括rules_text、abilities、attacks等。
        
        在处理玩家的自然语言请求时，如果请求涉及特定卡牌（包含UID），应该先使用此工具查询卡牌信息，以便：
        1. 理解卡牌的效果（rules_text）
        2. 了解卡牌的能力（abilities）和攻击（attacks）
        3. 确认操作是否符合卡牌的使用条件
        
        例如：如果玩家说"我想使用Charizard(uid:playerA-deck-016)的'Infernal Reign'能力"，
        你应该先调用 get_card_info 查询这张卡的信息，了解"Infernal Reign"能力的具体效果。
        """,
        args_schema=GetCardInfoInput,
    )

    get_game_state_tool = StructuredTool.from_function(
        func=get_game_state,
        name="get_game_state",
        description="""获取玩家的完整游戏状态信息，包括手牌、战斗区、备战区、牌库、弃牌区、奖赏卡等。
        
        **在处理玩家的自然语言请求前，应该先使用此工具获取游戏状态，以便：**
        1. 了解玩家手牌中有哪些卡牌（用于验证卡牌是否在手牌中）
        2. 了解场上的宝可梦情况（用于验证操作目标是否合法）
        3. 了解牌库和弃牌区情况（用于验证搜索、洗牌等操作）
        4. 了解奖赏卡数量（用于判断胜负条件）
        5. 了解对手状态（用于验证攻击目标等）
        
        这个工具应该在处理任何请求前调用，以便获得完整的上下文信息。
        """,
        args_schema=GetGameStateInput,
    )

    execute_action_tool = StructuredTool.from_function(
        func=execute_action,
        name="execute_action",
        description="""使用游戏工具执行已验证的行动。返回包含成功状态和数据的执行结果。

**⚠️ 重要：这个工具会实际执行操作并修改游戏状态。这不是模拟或假设，而是真实的游戏操作。**
- 这个工具会实际调用游戏工具集来执行操作
- 操作会真实地修改游戏状态（如移动卡牌、改变HP、更新回合状态等）
- 返回的结果是真实的执行结果，不是假设的结果
- **必须调用此工具来执行玩家的请求，不要假设或模拟操作结果**

使用此工具时，确保已经：
1. 获取了游戏状态（使用 get_game_state）
2. 理解了卡牌效果（使用 get_card_info）
3. 解析了玩家请求（使用 parse_player_request）
4. 验证了操作合法性（使用 validate_action，可选）

然后调用此工具实际执行操作。""",
        args_schema=ExecuteActionInput,
    )

    def parse_player_request(request_text: str, player_id: str) -> str:
        """从自然语言请求中解析出操作类型（action）和参数（payload）。
        
        这个工具会分析玩家的自然语言请求，提取出：
        1. 操作类型（如 attach_energy, play_trainer, move_to_bench 等）
        2. 操作参数（包括卡牌 UID、目标等）
        
        输入示例：
        - "我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"
        - "我想使用手牌中的Iono(uid:playerA-deck-037)"
        - "我想将手牌中的Pikachu(uid:playerA-deck-017)放置到备战区"
        - "我想结束回合"
        
        输出格式：
        {
            "action": "attach_energy",
            "payload": {
                "energy_card_id": "playerA-deck-020",
                "pokemon_id": "playerA-deck-015"
            }
        }
        
        如果请求是"结束回合"，返回：
        {
            "action": "end_turn",
            "payload": {}
        }
        
        如果请求不明确或缺少信息，返回错误信息。
        """
        logger.info(f"[Referee] parse_player_request 被调用")
        logger.info(f"[Referee] 玩家ID: {player_id}")
        logger.info(f"[Referee] 请求文本: {request_text}")
        
        # 提取所有 UID（格式：uid:xxxxx）
        uid_pattern = r'uid:([a-zA-Z0-9\-_]+)'
        uids = re.findall(uid_pattern, request_text)
        logger.info(f"[Referee] 提取到的UID: {uids}")
        
        # 获取游戏状态信息用于验证
        state = base_referee.state
        player_state = state.players.get(player_id)
        
        # 构建可用卡牌 UID 列表（用于验证）
        available_uids = set()
        if player_state:
            # 手牌
            for card in player_state.zone(Zone.HAND).cards:
                available_uids.add(card.uid)
            # 战斗区
            if player_state.zone(Zone.ACTIVE).cards:
                available_uids.add(player_state.zone(Zone.ACTIVE).cards[0].uid)
            # 备战区
            for card in player_state.zone(Zone.BENCH).cards:
                available_uids.add(card.uid)
        
        # 检查是否缺少 UID
        if not uids and "结束" not in request_text and "回合" in request_text:
            # 可能是结束回合的请求
            if "结束" in request_text or "不进行攻击" in request_text:
                return json.dumps({
                    "action": "end_turn",
                    "payload": {},
                    "message": "玩家选择结束回合"
                })
            return json.dumps({
                "error": True,
                "message": "请求中缺少卡牌 UID。请确保在请求中包含所有卡牌的 UID（格式：uid:xxxxx）",
                "hint": "例如：'我想使用手牌中的Iono(uid:playerA-deck-037)'"
            })
        
        # 根据请求内容识别操作类型
        request_lower = request_text.lower()
        
        # 先检查所有明确的操作类型（按优先级顺序）
        
        # 1. 附能操作
        if "附" in request_text or "attach" in request_lower or ("能量" in request_text and "附" in request_text):
            if len(uids) >= 2:
                return json.dumps({
                    "action": "attach_energy",
                    "payload": {
                        "energy_card_id": uids[0],
                        "pokemon_id": uids[1]
                    }
                })
            else:
                return json.dumps({
                    "error": True,
                    "message": "附能操作需要两个 UID：能量卡 UID 和目标宝可梦 UID",
                    "hint": "格式：'我想将手牌中的基础超能量(uid:xxxxx)附到Arceus V(uid:yyyyy)上'"
                })
        
        # 2. 放置到备战区
        if "放置" in request_text and "备战" in request_text:
            if uids:
                return json.dumps({
                    "action": "move_to_bench",
                    "payload": {
                        "card_id": uids[0]
                    }
                })
            else:
                return json.dumps({
                    "error": True,
                    "message": "放置宝可梦到备战区需要提供卡牌 UID",
                    "hint": "格式：'我想将手牌中的Pikachu(uid:xxxxx)放置到备战区'"
                })
        
        # 3. 进化
        if "进化" in request_text:
            if len(uids) >= 2:
                return json.dumps({
                    "action": "evolve_pokemon",
                    "payload": {
                        "base_card_id": uids[0],
                        "evolution_card_id": uids[1]
                    }
                })
            else:
                return json.dumps({
                    "error": True,
                    "message": "进化操作需要两个 UID：基础宝可梦 UID 和进化卡 UID",
                    "hint": "格式：'我想将Charmander(uid:xxxxx)进化为Charmeleon(uid:yyyyy)'"
                })
        
        # 4. 撤退/切换
        if "撤退" in request_text or ("切换" in request_text and "战斗" in request_text) or "retreat" in request_lower or ("switch" in request_lower and "active" in request_lower):
            if uids:
                return json.dumps({
                    "action": "switch_pokemon",
                    "payload": {
                        "bench_card_id": uids[0]
                    }
                })
            else:
                return json.dumps({
                    "error": True,
                    "message": "撤退操作需要提供备战区宝可梦 UID",
                    "hint": "格式：'我想将战斗区的Pikachu撤退，切换到备战区的Raichu(uid:xxxxx)'"
                })
        
        # 5. 使用能力
        if "能力" in request_text or "ability" in request_lower:
            if uids:
                # 尝试提取能力名称
                ability_match = re.search(r"['\"]([^'\"]+)['\"]", request_text)
                ability_name = ability_match.group(1) if ability_match else None
                if ability_name:
                    return json.dumps({
                        "action": "use_ability",
                        "payload": {
                            "card_id": uids[0],
                            "ability_name": ability_name
                        }
                    })
                else:
                    return json.dumps({
                        "error": True,
                        "message": "使用能力需要提供宝可梦 UID 和能力名称",
                        "hint": "格式：'我想使用Pikachu(uid:xxxxx)的'Thunder Shock'能力'"
                    })
            else:
                return json.dumps({
                    "error": True,
                    "message": "使用能力需要提供宝可梦 UID",
                    "hint": "格式：'我想使用Pikachu(uid:xxxxx)的'Thunder Shock'能力'"
                })
        
        # 6. 攻击（优先识别，即使玩家说"手牌中的"也要识别为攻击）
        # 攻击的宝可梦应该在战斗区，但玩家可能描述不准确（说"手牌中的"）
        if "攻击" in request_text or "attack" in request_lower:
            logger.info(f"[Referee] 检测到攻击关键词，尝试识别攻击请求")
            if uids:
                # 尝试提取攻击名称 - 支持多种格式
                attack_name = None
                # 格式1: "的'Attack Name'攻击"
                attack_match1 = re.search(r"的['\"]([^'\"]+)['\"]攻击", request_text)
                if attack_match1:
                    attack_name = attack_match1.group(1)
                    logger.info(f"[Referee] 从格式1提取攻击名称: {attack_name}")
                else:
                    # 格式2: "'Attack Name'攻击"
                    attack_match2 = re.search(r"['\"]([^'\"]+)['\"]攻击", request_text)
                    if attack_match2:
                        attack_name = attack_match2.group(1)
                        logger.info(f"[Referee] 从格式2提取攻击名称: {attack_name}")
                    else:
                        # 格式3: "使用...的Attack Name攻击"（没有引号）
                        attack_match3 = re.search(r"的([^'\"的]+)攻击", request_text)
                        if attack_match3:
                            potential_name = attack_match3.group(1).strip()
                            # 过滤掉太短或明显不是攻击名称的内容
                            if len(potential_name) > 2 and "uid" not in potential_name:
                                attack_name = potential_name
                                logger.info(f"[Referee] 从格式3提取攻击名称: {attack_name}")
                
                payload = {
                    "card_id": uids[0],
                }
                if attack_name:
                    payload["attack_name"] = attack_name
                else:
                    logger.warning(f"[Referee] 未能提取攻击名称，但继续识别为攻击操作")
                if len(uids) >= 2:
                    payload["target_pokemon_id"] = uids[1]
                
                logger.info(f"[Referee] 识别为攻击操作: action=use_attack, payload={payload}")
                return json.dumps({
                    "action": "use_attack",
                    "payload": payload
                })
            else:
                logger.warning(f"[Referee] 检测到攻击关键词但未找到UID")
                return json.dumps({
                    "error": True,
                    "message": "攻击操作需要提供宝可梦 UID",
                    "hint": "格式：'我想使用Charizard(uid:xxxxx)的'Blaze'攻击' 或 '我想使用战斗区的Jirachi(uid:xxxxx)的'Charge Energy'攻击'"
                })
        
        # 7. 使用训练家卡（作为默认情况：包含"使用"和UID，且没有匹配上述操作类型）
        if "使用" in request_text and uids:
            result = {
                "action": "play_trainer",
                "payload": {
                    "card_id": uids[0]
                }
            }
            logger.info(f"[Referee] 识别为使用训练家卡操作: {result}")
            return json.dumps(result)
        
        # 也支持明确提到训练家相关关键词的情况（即使没有UID，也给出提示）
        if "使用" in request_text and ("训练家" in request_text or "trainer" in request_lower or 
                                       "supporter" in request_lower or "item" in request_lower or
                                       "stadium" in request_lower or "tool" in request_lower):
            if uids:
                return json.dumps({
                    "action": "play_trainer",
                    "payload": {
                        "card_id": uids[0]
                    }
                })
            else:
                return json.dumps({
                    "error": True,
                    "message": "使用训练家卡需要提供卡牌 UID",
                    "hint": "格式：'我想使用手牌中的Iono(uid:xxxxx)'"
                })
        
        # 如果无法识别，返回错误
        error_result = {
            "error": True,
            "message": f"无法识别请求类型。请确保请求包含明确的操作意图和必要的 UID。",
            "hint": "支持的操作：附能、使用训练家卡、放置宝可梦、进化、撤退、使用能力、攻击、结束回合",
            "request": request_text
        }
        logger.warning(f"[Referee] 无法识别请求类型: {error_result}")
        return json.dumps(error_result)

    parse_player_request_tool = StructuredTool.from_function(
        func=parse_player_request,
        name="parse_player_request",
        description="""从玩家的自然语言请求中解析出操作类型和参数。
        
        这个工具会分析玩家的自然语言请求，提取出操作类型（action）和参数（payload）。
        支持的请求类型包括：
        - 附能：包含"附"、"能量"等关键词，需要两个 UID（能量卡和目标宝可梦）
        - 使用训练家卡：包含"使用"和训练家相关关键词，需要一个 UID
        - 放置宝可梦：包含"放置"和"备战"，需要一个 UID
        - 进化：包含"进化"，需要两个 UID（基础宝可梦和进化卡）
        - 撤退：包含"撤退"或"切换"，需要一个 UID（备战区宝可梦）
        - 使用能力：包含"能力"，需要 UID 和能力名称
        - 攻击：包含"攻击"，需要 UID 和攻击名称（可选目标）
        - 结束回合：包含"结束回合"或"不进行攻击"
        
        所有请求必须包含卡牌的 UID（格式：uid:xxxxx）。
        如果请求不明确或缺少信息，会返回错误提示。
        """,
        args_schema=ParsePlayerRequestInput,
    )

    query_deck_candidates_tool = StructuredTool.from_function(
        func=query_deck_candidates,
        name="query_deck_candidates",
        description="""查询牌库中符合条件的候选卡牌，返回候选列表但不执行移动操作。
        
        这个工具用于需要玩家选择的操作（如Nest Ball搜索基础宝可梦、Level Ball搜索HP≤90的宝可梦等），
        返回候选列表供玩家选择。
        
        使用场景：
        - Nest Ball: 搜索基础宝可梦 -> query_deck_candidates(card_type="Pokemon", stage="Basic")
        - Level Ball: 搜索HP≤90的宝可梦 -> query_deck_candidates(card_type="Pokemon", max_hp=90)
        - 搜索能量卡 -> query_deck_candidates(card_type="Energy", energy_type="Basic Energy")
        """,
        args_schema=QueryDeckCandidatesInput,
    )

    query_discard_candidates_tool = StructuredTool.from_function(
        func=query_discard_candidates,
        name="query_discard_candidates",
        description="""查询弃牌堆中符合条件的候选卡牌，返回候选列表但不执行移动操作。
        
        这个工具用于需要玩家选择的操作（如Super Rod从弃牌堆选择宝可梦或基础能量卡），
        返回候选列表供玩家选择。
        
        使用场景：
        - Super Rod: 从弃牌堆选择宝可梦或基础能量卡 -> query_discard_candidates(card_type="Pokemon") 或 query_discard_candidates(energy_type="Basic Energy")
        """,
        args_schema=QueryDiscardCandidatesInput,
    )

    return [parse_player_request_tool, validate_action_tool, check_rules_tool, query_rule_tool, get_card_info_tool, get_game_state_tool, query_deck_candidates_tool, query_discard_candidates_tool, execute_action_tool]

