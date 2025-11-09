"""Core analysis logic for Rule Analyst Agent."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.ptcg_ai.models import CardDefinition
from .pattern_matcher import RulePatternMatcher
from .rulebook_query import RulebookQuery, create_rulebook_query

logger = logging.getLogger(__name__)


@dataclass
class CardExecutionPlan:
    """卡牌执行预案数据结构"""
    
    card_id: str  # 格式：set_code-number
    card_name: str
    set_code: str
    number: str
    
    # 效果类型
    effect_type: Optional[str] = None  # attack, ability, trainer, energy
    effect_subtype: Optional[str] = None  # 子类型：Item, Supporter, Stadium, Tool, Basic Energy等
    effect_name: Optional[str] = None  # 效果名称（如攻击名称、能力名称等）
    
    # 效果分析
    requires_selection: bool = False  # 是否需要玩家选择
    selection_source: Optional[str] = None  # 选择来源：deck, discard, hand等
    selection_criteria: Optional[Dict[str, Any]] = None  # 选择条件
    max_selection_count: Optional[int] = None  # 最大选择数量
    min_selection_count: int = 0  # 最小选择数量（0表示可选）
    selection_target: Optional[str] = None  # 选择目标（特殊情况下覆盖_determine_target的结果，如Nest Ball放到bench）
    
    # 执行流程
    execution_steps: List[Dict[str, Any]] = None  # 执行步骤列表
    # 每个步骤包含：
    # - step_type: validation, query, selection, move, damage, shuffle, check等
    # - description: 中文描述
    # - action: 具体操作（如query_deck_candidates, move_cards等）
    # - params: 操作参数
    # - depends_on: 依赖的步骤索引列表
    # - optional: 是否为可选步骤
    # - skip_if: 跳过条件
    
    # 规则限制
    restrictions: List[Dict[str, Any]] = None  # 使用限制
    
    # 验证规则
    validation_rules: List[Dict[str, Any]] = None  # 验证规则列表
    # 每个验证规则包含：
    # - type: 验证类型（bench_full, energy_requirement, in_active, ability_used, turn_limit等）
    # - description: 验证描述
    # - params: 验证参数
    # - error_message: 失败时的错误消息
    
    # 状态
    status: str = "draft"  # draft, reviewed, approved, deprecated
    reviewed_by: Optional[str] = None  # 审核人
    reviewed_at: Optional[datetime] = None  # 审核时间
    version: int = 1  # 版本号
    
    # 元数据
    analysis_notes: Optional[str] = None  # 分析备注
    
    # 规则文档引用
    rulebook_references: List[Dict[str, Any]] = None  # 相关规则文档引用列表
    # 每个引用包含：
    # - rule_id: 规则ID（如 "C-06", "B-08"）
    # - filename: 文档文件名
    # - summary: 规则摘要
    # - pattern_type: 匹配的模式类型
    
    def __post_init__(self):
        """初始化默认值"""
        if self.execution_steps is None:
            self.execution_steps = []
        if self.restrictions is None:
            self.restrictions = []
        if self.validation_rules is None:
            self.validation_rules = []
        if self.rulebook_references is None:
            self.rulebook_references = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于数据库存储"""
        data = asdict(self)
        # 处理datetime对象
        if data.get("reviewed_at") and isinstance(data["reviewed_at"], datetime):
            data["reviewed_at"] = data["reviewed_at"].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CardExecutionPlan":
        """从字典创建对象，用于从数据库加载"""
        # 处理datetime字符串
        if data.get("reviewed_at") and isinstance(data["reviewed_at"], str):
            try:
                data["reviewed_at"] = datetime.fromisoformat(data["reviewed_at"])
            except:
                data["reviewed_at"] = None
        return cls(**data)


def analyze_card_effect(card_definition: CardDefinition) -> CardExecutionPlan:
    """分析卡牌效果并生成执行预案。
    
    注意：对于有多个能力/攻击的宝可梦，此函数只返回第一个效果的预案。
    如果需要所有效果的预案，请使用 analyze_all_card_effects 函数。
    
    Args:
        card_definition: 卡牌定义对象
        
    Returns:
        CardExecutionPlan对象（第一个效果的预案）
    """
    all_plans = analyze_all_card_effects(card_definition)
    if all_plans:
        return all_plans[0]
    else:
        # 如果没有效果，返回一个空的 plan
        card_id = f"{card_definition.set_code}-{card_definition.number}"
        return CardExecutionPlan(
            card_id=card_id,
            card_name=card_definition.name,
            set_code=card_definition.set_code,
            number=card_definition.number,
        )


def analyze_all_card_effects(card_definition: CardDefinition, rulebook_query: Optional[RulebookQuery] = None) -> List[CardExecutionPlan]:
    """分析卡牌的所有效果并生成执行预案列表。
    
    对于有多个能力/攻击的宝可梦，为每个能力/攻击创建独立的预案。
    
    Args:
        card_definition: 卡牌定义对象
        rulebook_query: 规则文档查询器（可选，如果为None则自动创建）
        
    Returns:
        CardExecutionPlan对象列表，每个效果一个预案
    """
    logger.info(f"[RuleAnalyst] 开始分析卡牌: {card_definition.name} ({card_definition.set_code}-{card_definition.number})")
    
    # 创建规则文档查询器（如果未提供）
    if rulebook_query is None:
        rulebook_query = create_rulebook_query()
    
    # 生成card_id
    card_id = f"{card_definition.set_code}-{card_definition.number}"
    
    plans = []
    
    # 根据卡牌类型分析
    if card_definition.card_type == "Pokemon":
        # 为每个能力创建独立的预案
        if card_definition.abilities:
            for ability in card_definition.abilities:
                plan = CardExecutionPlan(
                    card_id=card_id,
                    card_name=card_definition.name,
                    set_code=card_definition.set_code,
                    number=card_definition.number,
                )
                _analyze_ability(plan, card_definition, ability)
                _analyze_restrictions(plan, card_definition)
                # 查询相关规则文档
                _query_rulebook_references(plan, ability.get("text", ""), rulebook_query)
                plans.append(plan)
        
        # 为每个攻击创建独立的预案
        if card_definition.attacks:
            for attack in card_definition.attacks:
                plan = CardExecutionPlan(
                    card_id=card_id,
                    card_name=card_definition.name,
                    set_code=card_definition.set_code,
                    number=card_definition.number,
                )
                _analyze_attack(plan, card_definition, attack)
                _analyze_restrictions(plan, card_definition)
                # 查询相关规则文档
                attack_text = attack.get("text", "") or attack.get("name", "")
                _query_rulebook_references(plan, attack_text, rulebook_query)
                plans.append(plan)
    
    elif card_definition.card_type == "Trainer":
        # 训练家卡只有一个效果
        plan = CardExecutionPlan(
            card_id=card_id,
            card_name=card_definition.name,
            set_code=card_definition.set_code,
            number=card_definition.number,
        )
        
        # 确定子类型（放宽匹配并优先识别 Tool）
        subtypes = card_definition.subtypes or []
        lower_subtypes = [s.lower() for s in subtypes]
        if any("tool" in s for s in lower_subtypes):
            plan.effect_subtype = "Tool"
        elif any(s == "stadium" for s in lower_subtypes):
            plan.effect_subtype = "Stadium"
        elif any(s == "supporter" for s in lower_subtypes):
            plan.effect_subtype = "Supporter"
        elif any(s == "item" for s in lower_subtypes):
            plan.effect_subtype = "Item"
        
        plan.effect_type = "trainer"
        
        # 分析训练家卡效果
        if card_definition.rules_text:
            _analyze_trainer_effect(plan, card_definition)
            # 查询相关规则文档
            _query_rulebook_references(plan, card_definition.rules_text, rulebook_query)
        
        _analyze_restrictions(plan, card_definition)
        plans.append(plan)
    
    elif card_definition.card_type == "Energy":
        # 能量卡只有一个效果
        plan = CardExecutionPlan(
            card_id=card_id,
            card_name=card_definition.name,
            set_code=card_definition.set_code,
            number=card_definition.number,
        )
        
        plan.effect_type = "energy"
        if "Basic" in (card_definition.subtypes or []):
            plan.effect_subtype = "Basic Energy"
        
        _analyze_energy_effect(plan, card_definition)
        _analyze_restrictions(plan, card_definition)
        plans.append(plan)
    
    logger.info(f"[RuleAnalyst] 分析完成: 生成了 {len(plans)} 个预案")
    for plan in plans:
        logger.info(f"  - {plan.effect_type} {plan.effect_name or '(无名称)'}: {len(plan.execution_steps)} 个步骤")
    
    return plans


def _analyze_ability(plan: CardExecutionPlan, card_def: CardDefinition, ability: Dict[str, Any]) -> None:
    """分析宝可梦能力效果，修改传入的 plan 对象。"""
    ability_name = ability.get("name", "")
    ability_text = ability.get("text", "").lower()
    
    plan.effect_type = "ability"
    plan.effect_name = ability_name
    
    # 确保execution_steps已初始化
    if plan.execution_steps is None:
        plan.execution_steps = []
    
    # 检查是否为被动能力
    is_passive = (
        "prevent" in ability_text or
        "as long as" in ability_text or
        "whenever" in ability_text or
        ("once during your turn" not in ability_text and "you may" not in ability_text)
    )
    
    if is_passive:
        # 被动能力无需执行步骤
        plan.execution_steps = []
        plan.analysis_notes = "被动能力，自动生效"
        return
    
    # 确保validation_rules已初始化
    if plan.validation_rules is None:
        plan.validation_rules = []
    
    # 检查已存在的验证规则类型，避免重复添加
    existing_types = {rule.get("type") for rule in plan.validation_rules}
    
    # 主动能力：添加验证规则
    # 检查是否在战斗区
    if ("if this pokémon is in the active spot" in ability_text or "active spot" in ability_text) and "in_active" not in existing_types:
        plan.validation_rules.append({
            "type": "in_active",
            "description": "这个宝可梦必须在战斗区",
            "params": {},
            "error_message": f"能力'{ability_name}'只能在战斗区使用"
        })
    
    # 检查使用次数限制（每个能力的使用限制不同，需要检查ability_name）
    if "once during your turn" in ability_text:
        # 检查是否已有相同ability_name的规则
        has_same_ability = False
        for rule in plan.validation_rules:
            if rule.get("type") == "ability_used":
                existing_name = rule.get("params", {}).get("ability_name")
                if existing_name == ability_name:
                    has_same_ability = True
                    break
        
        if not has_same_ability:
            plan.validation_rules.append({
                "type": "ability_used",
                "description": "本回合是否已使用过此能力",
                "params": {"ability_name": ability_name},
                "error_message": f"能力'{ability_name}'本回合已使用过"
            })
    
    if "once during your game" in ability_text or "once per game" in ability_text:
        # 检查是否已有相同ability_name的规则
        has_same_ability = False
        for rule in plan.validation_rules:
            if rule.get("type") == "ability_used_game":
                existing_name = rule.get("params", {}).get("ability_name")
                if existing_name == ability_name:
                    has_same_ability = True
                    break
        
        if not has_same_ability:
            plan.validation_rules.append({
                "type": "ability_used_game",
                "description": "本局游戏是否已使用过此能力",
                "params": {"ability_name": ability_name},
                "error_message": f"能力'{ability_name}'本局游戏已使用过"
            })
    
    # 分析能力效果文本
    _analyze_effect_text(plan, ability_text, ability_name)


def _analyze_attack(plan: CardExecutionPlan, card_def: CardDefinition, attack: Dict[str, Any]) -> None:
    """分析宝可梦攻击效果，修改传入的 plan 对象。"""
    attack_name = attack.get("name", "")
    attack_text = attack.get("text", "").lower()
    attack_damage = attack.get("damage", "")
    attack_cost = attack.get("cost", [])
    
    plan.effect_type = "attack"
    plan.effect_name = attack_name
    
    # 确保execution_steps已初始化
    if plan.execution_steps is None:
        plan.execution_steps = []
    
    # 确保validation_rules已初始化
    if plan.validation_rules is None:
        plan.validation_rules = []
    
    # 检查已存在的验证规则类型，避免重复添加
    existing_types = {rule.get("type") for rule in plan.validation_rules}
    
    # 添加验证规则（如果不存在）
    # 检查是否在战斗区
    if "in_active" not in existing_types:
        plan.validation_rules.append({
            "type": "in_active",
            "description": "宝可梦必须在战斗区才能使用攻击",
            "params": {},
            "error_message": "只有战斗区的宝可梦才能使用攻击"
        })
    
    # 检查能量需求
    # 注意：对于多个攻击，我们只需要一个通用的 energy_requirement 验证规则
    # 因为验证时会检查当前使用的攻击的 cost，所以不需要为每个攻击单独添加规则
    if attack_cost:
        # 检查是否已有 energy_requirement 类型的规则（不管 cost 是什么）
        has_energy_requirement = any(
            rule.get("type") == "energy_requirement" 
            for rule in plan.validation_rules
        )
        
        if not has_energy_requirement:
            # 只添加一次通用的能量需求验证规则
            plan.validation_rules.append({
                "type": "energy_requirement",
                "description": "检查附着能量是否满足招式需求",
                "params": {"cost": attack_cost},  # 保存第一个攻击的 cost 作为示例
                "error_message": "攻击的能量需求未满足"
            })
    
    # 添加伤害结算步骤
    if attack_damage:
        try:
            base_damage = int(str(attack_damage).replace("+", "").split()[0])
        except:
            base_damage = 0
        
        # 使用 RulePatternMatcher 解析伤害计算
        damage_calc = RulePatternMatcher.parse_damage_calculation(attack_text)
        damage_modifiers = _parse_damage_modifiers(attack_text, damage_calc)
        
        plan.execution_steps.append({
            "step_type": "damage",
            "description": "结算招式伤害",
            "action": "calculate_and_apply_damage",
            "params": {
                "base_damage": base_damage,
                "damage_modifiers": damage_modifiers,
                "damage_calculation": damage_calc  # 添加新的伤害计算信息
            },
            "depends_on": [],
            "optional": False
        })
    
    # 分析攻击效果文本
    _analyze_effect_text(plan, attack_text, attack_name)


def _analyze_trainer_effect(plan: CardExecutionPlan, card_def: CardDefinition) -> None:
    """分析训练家卡效果"""
    rules_text = card_def.rules_text or ""
    rules_text_lower = rules_text.lower()
    
    # 添加验证规则
    validation_rules = []
    
    # 检查卡牌是否在手牌中
    validation_rules.append({
        "type": "in_hand",
        "description": "卡牌必须在手牌中",
        "params": {},
        "error_message": "训练家卡必须从手牌中使用"
    })
    
    # 使用模式匹配器解析条件限制
    conditions = RulePatternMatcher.parse_condition_clauses(rules_text)
    for condition in conditions:
        if condition.get("type") == "prize_comparison":
            validation_rules.append({
                "type": "prize_comparison",
                "description": condition.get("description", "奖赏卡数量比较"),
                "params": {},
                "error_message": condition.get("error_message", "奖赏卡数量条件不满足")
            })
        elif condition.get("type") == "turn_limit":
            validation_rules.append({
                "type": "turn_limit",
                "value": condition.get("value", 1),
                "condition": condition.get("condition", "first_turn"),
                "description": condition.get("description", "回合限制")
            })
    
    # 基于 subtype 的通用处理
    if plan.effect_subtype == "Supporter":
        validation_rules.append({
            "type": "supporter_used",
            "description": "本回合是否已使用过Supporter卡",
            "params": {},
            "error_message": "每回合只能使用一张Supporter卡"
        })
        validation_rules.append({
            "type": "first_turn_restriction",
            "description": "先手玩家第一回合不能使用Supporter卡",
            "params": {},
            "error_message": "先手玩家第一回合不能使用Supporter卡"
        })
    
    elif plan.effect_subtype == "Stadium":
        validation_rules.append({
            "type": "stadium_used",
            "description": "本回合是否已使用过Stadium卡",
            "params": {},
            "error_message": "每回合只能使用一张Stadium卡"
        })
        validation_rules.append({
            "type": "stadium_duplicate",
            "description": "场上是否已有同名Stadium",
            "params": {},
            "error_message": "场上不能同时存在两张同名Stadium卡"
        })
    
    elif plan.effect_subtype == "Tool":
        validation_rules.append({
            "type": "tool_attached",
            "description": "目标宝可梦是否已有道具",
            "params": {},
            "error_message": "每只宝可梦只能附着一张道具卡"
        })
    
    # 解析规则文本中的条件限制（基于文本模式，而非卡牌名称）
    # "Discard X, and..." 表示需要先丢弃手牌
    discard_match = re.search(r"discard (\d+) (?:cards? )?from your hand", rules_text_lower)
    if discard_match:
        count = int(discard_match.group(1))
        validation_rules.append({
            "type": "hand_size",
            "description": f"手牌中是否有至少{count}张其他卡牌",
            "params": {"min_other_cards": count},
            "error_message": f"手牌中必须有至少{count}张其他卡牌才能使用"
        })
    
    # "Shuffle... from your discard pile into your deck" 表示需要弃牌区有卡
    if "from your discard pile" in rules_text_lower and "into your deck" in rules_text_lower:
        # 检查是否有卡牌类型限制
        if "pokémon" in rules_text_lower or "energy" in rules_text_lower:
            validation_rules.append({
                "type": "discard_has_cards",
                "description": "弃牌区中是否有符合条件的卡牌",
                "params": {"card_types": ["Pokemon", "Basic Energy"]},
                "error_message": "弃牌区中必须有符合条件的卡牌才能使用"
            })
    
    # "You may discard a Stadium in play. If you do..." 表示需要场上有Stadium或Tool
    if "you may discard" in rules_text_lower and ("stadium" in rules_text_lower or "tool" in rules_text_lower):
        validation_rules.append({
            "type": "stadium_or_tool_in_play",
            "description": "场上是否存在竞技场卡或道具卡",
            "params": {},
            "error_message": "场上必须存在竞技场卡或道具卡才能使用"
        })
    
    # "put them onto your Bench" 表示需要备战区有空位
    if "onto your bench" in rules_text_lower or "onto the bench" in rules_text_lower:
        validation_rules.append({
            "type": "bench_space",
            "description": "备战区是否有空位",
            "params": {},
            "error_message": "备战区必须有空位才能使用"
        })
        # 设置目标为bench
        plan.selection_target = "bench"
    
    # "Switch your Active Pokémon with 1 of your Benched Pokémon" 表示需要备战区有宝可梦
    if "switch" in rules_text_lower and "benched pokémon" in rules_text_lower:
        validation_rules.append({
            "type": "bench_has_pokemon",
            "description": "备战区是否有宝可梦",
            "params": {},
            "error_message": "备战区必须有宝可梦才能使用"
        })
    
    plan.validation_rules.extend(validation_rules)
    
    # 分析效果文本
    _analyze_effect_text(plan, rules_text, card_def.name)


def _analyze_energy_effect(plan: CardExecutionPlan, card_def: CardDefinition) -> None:
    """分析能量卡效果"""
    # 基础能量卡：添加验证规则
    validation_rules = []
    
    validation_rules.append({
        "type": "in_hand",
        "description": "能量卡必须在手牌中",
        "params": {},
        "error_message": "能量卡必须从手牌中附着"
    })
    
    validation_rules.append({
        "type": "energy_attachment_limit",
        "description": "本回合是否已附能过",
        "params": {},
        "error_message": "每回合只能从手牌附能一次"
    })
    
    plan.validation_rules.extend(validation_rules)
    
    # 添加附能步骤
    plan.execution_steps.append({
        "step_type": "move",
        "description": "将能量卡附着到玩家选择的宝可梦上",
        "action": "attach_energy",
        "params": {
            "target": "pokemon"  # 战斗区或备战区
        },
        "depends_on": [],
        "optional": False
    })


def _analyze_effect_text(plan: CardExecutionPlan, effect_text: str, effect_name: str) -> None:
    """分析效果文本，生成执行步骤（基于规则文本模式，而非卡牌名称）"""
    # 确保execution_steps已初始化
    if plan.execution_steps is None:
        plan.execution_steps = []
    
    steps = []
    base_step_index = len(plan.execution_steps)  # 从已有步骤后开始（用于最终添加到plan.execution_steps时的索引偏移）
    effect_text_lower = effect_text.lower()
    
    def get_step_index(offset: int = 0) -> int:
        """获取当前步骤的索引（相对于base_step_index）"""
        return base_step_index + len(steps) + offset

    # Ultra Ball 等：在检索前强制处理 “discard N cards from your hand”
    pre_discard_added = False
    m_discard_first = re.search(r"discard\s+(\d+)\s+cards?\s+from\s+your\s+hand.*search\s+your\s+deck", effect_text_lower)
    if m_discard_first:
        n = int(m_discard_first.group(1))
        steps.append({
            "step_type": "selection",
            "description": f"询问玩家选择要丢弃的{n}手牌",
            "action": "wait_for_selection",
            "params": {"source": "hand", "max_count": n, "min_count": n},
            "depends_on": [],
            "optional": False
        })
        steps.append({
            "step_type": "move",
            "description": f"将选择的{n}张手牌移到弃牌堆",
            "action": "move_cards",
            "params": {"source": "hand", "target": "discard"},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
        pre_discard_added = True
    
    # Ultra Ball 变体2："You can use this card only if you discard N other cards from your hand."
    if not pre_discard_added:
        m_discard_only_if = re.search(r"only\s+if\s+you\s+discard\s+(\d+)\s+(?:other\s+)?cards?(?:\s+from\s+your\s+hand)?", effect_text_lower)
        if m_discard_only_if:
            n = int(m_discard_only_if.group(1))
            steps.append({
                "step_type": "selection",
                "description": f"询问玩家选择要丢弃的{n}手牌",
                "action": "wait_for_selection",
                "params": {"source": "hand", "max_count": n, "min_count": n},
                "depends_on": [],
                "optional": False
            })
            steps.append({
                "step_type": "move",
                "description": f"将选择的{n}张手牌移到弃牌堆",
                "action": "move_cards",
                "params": {"source": "hand", "target": "discard"},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
            pre_discard_added = True
    
    # 检查是否为多玩家操作
    is_multi_player = RulePatternMatcher.is_multi_player(effect_text)
    
    # 使用模式匹配器解析操作序列（包括 before_damage 标记）
    actions = RulePatternMatcher.parse_action_sequence(effect_text)
    search_action = next((a for a in actions if a.get("type") == "search"), None)
    
    # Iono 专属：底部洗牌 + 按奖赏抽牌（each player ... bottom of their deck）
    if ("each player" in effect_text_lower and "shuffles" in effect_text_lower and
        "hand" in effect_text_lower and "bottom of" in effect_text_lower and "deck" in effect_text_lower):
        steps.append({
            "step_type": "move",
            "description": "双方将手牌以随机的顺序放回到各自牌库底部",
            "action": "shuffle_hand_into_deck_bottom",
            "params": {"both_players": True},
            "depends_on": [],
            "optional": False
        })
        steps.append({
            "step_type": "draw",
            "description": "双方各自根据剩余奖赏卡数量抽牌",
            "action": "draw_cards_by_prizes",
            "params": {"both_players": True},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
        # 继续处理其余文本（若有）

    # Lost Vacuum（常见原文变体）：only if you put another card from your hand in the Lost Zone ... discard a Tool/Stadium
    if ("only if you put" in effect_text_lower and "from your hand" in effect_text_lower and
        "lost zone" in effect_text_lower and ("stadium" in effect_text_lower or "tool" in effect_text_lower)):
        # 先从手牌放一张卡到Lost Zone
        steps.append({
            "step_type": "selection",
            "description": "询问玩家选择一张手牌放入Lost Zone（作为使用条件）",
            "action": "wait_for_selection",
            "params": {"source": "hand", "max_count": 1, "min_count": 1},
            "depends_on": [],
            "optional": False
        })
        steps.append({
            "step_type": "move",
            "description": "将选择的手牌放到Lost Zone",
            "action": "move_cards",
            "params": {"source": "hand", "target": "lost_zone"},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
        # 丢弃场上的Tool/Stadium
        steps.append({
            "step_type": "query",
            "description": "查询场上的竞技场卡或道具卡",
            "action": "query_stadium_and_tools",
            "params": {},
            "depends_on": [],
            "optional": False
        })
        steps.append({
            "step_type": "selection",
            "description": "询问玩家选择要丢弃的竞技场卡或道具卡",
            "action": "wait_for_selection",
            "params": {"max_count": 1, "min_count": 1},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
        steps.append({
            "step_type": "move",
            "description": "将选择的竞技场卡或道具卡放入Lost Zone",
            "action": "move_cards",
            "params": {"target": "lost_zone"},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
    
    # 检查是否需要选择
    if search_action or "search" in effect_text or "choose" in effect_text or "look at" in effect_text:
        plan.requires_selection = True
        
        if search_action:
            # 使用模式匹配器解析的结果
            plan.selection_source = search_action.get("source", "deck")
            plan.selection_criteria = search_action.get("criteria", {})
            # 从criteria中提取max_count
            if "max_count" in plan.selection_criteria:
                plan.max_selection_count = plan.selection_criteria.pop("max_count")
            else:
                plan.max_selection_count = 1
            plan.min_selection_count = 0
        else:
            # 回退到原有逻辑（用于"choose"和"look at"）
            # 识别选择来源
            if "deck" in effect_text:
                plan.selection_source = "deck"
            elif "discard" in effect_text or "discard pile" in effect_text:
                plan.selection_source = "discard"
            elif "hand" in effect_text:
                plan.selection_source = "hand"
            
            # 使用模式匹配器解析选择条件
            if "search your deck" in effect_text_lower:
                match = RulePatternMatcher.SEARCH_DECK.search(effect_text)
                if match:
                    criteria_text = match.group(1).strip()
                    plan.selection_criteria = RulePatternMatcher._parse_search_criteria(criteria_text)
                else:
                    plan.selection_criteria = {}
            else:
                # 对于"choose"和"look at"，使用简化解析
                plan.selection_criteria = RulePatternMatcher._parse_search_criteria(effect_text)
            
            # 识别选择数量
            up_to_match = re.search(r"up to (\d+)", effect_text)
            if up_to_match:
                plan.max_selection_count = int(up_to_match.group(1))
                plan.min_selection_count = 0
            else:
                plan.max_selection_count = 1
                plan.min_selection_count = 0
        
        # Ultra Ball 前置丢弃（若文本包含 discard N cards from your hand 且存在检索）
        discard_n = None
        m_dis = re.search(r"discard\s+(\d+)\s+cards?\s+from\s+your\s+hand", effect_text_lower)
        if m_dis and (search_action or "search your deck" in effect_text_lower):
            discard_n = int(m_dis.group(1))
            steps.append({
                "step_type": "selection",
                "description": f"询问玩家选择要丢弃的{discard_n}手牌",
                "action": "wait_for_selection",
                "params": {"source": "hand", "max_count": discard_n, "min_count": discard_n},
                "depends_on": [],
                "optional": False
            })
            steps.append({
                "step_type": "move",
                "description": f"将选择的{discard_n}张手牌移到弃牌堆",
                "action": "move_cards",
                "params": {"source": "hand", "target": "discard"},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })

        # Super Rod：若文本包含 from your discard pile ... into your deck，覆盖默认目标为 deck
        if plan.selection_source == "discard" and "into your deck" in effect_text_lower:
            plan.selection_target = "deck"
        
        # 添加查询步骤
        if plan.selection_source == "deck":
            steps.append({
                "step_type": "query",
                "description": f"查询牌库中符合条件的卡牌",
                "action": "query_deck_candidates",
                "params": plan.selection_criteria or {},
                "depends_on": [],
                "optional": False
            })
        elif plan.selection_source == "discard":
            steps.append({
                "step_type": "query",
                "description": f"查询弃牌区中符合条件的卡牌",
                "action": "query_discard_candidates",
                "params": plan.selection_criteria or {},
                "depends_on": [],
                "optional": False
            })
        
        # 添加选择步骤
        steps.append({
            "step_type": "selection",
            "description": "询问玩家的选择",
            "action": "wait_for_selection",
            "params": {
                "max_count": plan.max_selection_count,
                "min_count": plan.min_selection_count
            },
            "depends_on": [get_step_index(-1)] if len(steps) > 0 else [],
            "optional": plan.min_selection_count == 0
        })
        
        # 检查是否需要附着能量（而不是移动到hand/bench）
        if "attach" in effect_text and ("energy" in effect_text or "to your pokémon" in effect_text or "to your pokemon" in effect_text):
            # 能量附着：每张能量卡可以附着到不同的宝可梦
            steps.append({
                "step_type": "attach",
                "description": "将玩家选择的能量卡附着到玩家选择的宝可梦身上（任意方式）",
                "action": "attach_energy_cards",
                "params": {
                    "source": plan.selection_source,
                    "allow_multiple_targets": True,  # 允许每张能量卡附着到不同的宝可梦
                    "target_type": "pokemon"  # 可以附着到战斗区或备战区的宝可梦
                },
                "depends_on": [get_step_index(-1)],
                "optional": plan.min_selection_count == 0  # 如果可以不选择，则此步骤可选
            })
        else:
            # 普通移动步骤
            # 检查是否有特殊的目标设置（如Nest Ball）
            target = getattr(plan, 'selection_target', None) or _determine_target(effect_text)
            steps.append({
                "step_type": "move",
                "description": f"将玩家选择的卡牌移动到{target}",
                "action": "move_cards",
                "params": {
                    "source": plan.selection_source,
                    "target": target
                },
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
    
    # 检查查看牌库上方N张
    if "look at the top" in effect_text or "reveal the top" in effect_text:
        top_match = re.search(r"top (\d+)", effect_text)
        if top_match:
            count = int(top_match.group(1))
            steps.append({
                "step_type": "query",
                "description": f"查看牌库上方的{count}张牌",
                "action": "reveal_top_cards",
                "params": {"count": count},
                "depends_on": [],
                "optional": False
            })
    
    # 检查是否已经通过search action处理了Super Rod类型的操作
    super_rod_handled = any(s.get("action") == "query_discard_candidates" for s in steps) and \
                       "from your discard pile" in effect_text_lower and \
                       "into your deck" in effect_text_lower
    
    # 初始化 lost_vacuum_handled 标志（在使用之前）
    lost_vacuum_handled = False
    
    # 分离 before_damage 动作和常规动作
    before_damage_actions = [a for a in actions if a.get("before_damage")]
    regular_actions = [a for a in actions if not a.get("before_damage")]
    
    # 先处理 before_damage 动作（这些需要在伤害计算前执行）
    for action in before_damage_actions:
        # before_damage 动作会在下面的处理逻辑中统一处理
        # 但需要确保它们在伤害步骤之前执行
        pass
    
    # 处理常规操作序列（包括 before_damage 动作，因为它们也需要被处理）
    # 但跳过已经通过特殊逻辑处理的action（如Lost Vacuum）
    all_actions = before_damage_actions + regular_actions
    for action in all_actions:
        # 如果已经通过特殊逻辑处理了（如Lost Vacuum），跳过
        if lost_vacuum_handled and action.get("type") in ["discard_stadium", "move"] and "lost zone" in effect_text_lower:
            continue
        if action["type"] == "discard":
            # 丢弃操作
            count = action.get("count", 1)
            source = action.get("source", "hand")
            card_type = action.get("card_type", "")
            
            # 检查是否是"Discard all cards attached"（不应该被解析为丢弃手牌）
            if isinstance(count, str) and count == "all" and "attached" in effect_text_lower:
                # 这是"Discard all cards attached to that Pokémon"，已经在move_to_hand中处理
                continue
            
            # 格式化描述
            if isinstance(count, int):
                count_desc = f"{count}张"
            elif count == "all":
                count_desc = "所有"
            else:
                count_desc = str(count)
            
            if source == "hand":
                # 避免与前置丢弃重复（Ultra Ball）
                if pre_discard_added and "search your deck" in effect_text_lower:
                    continue
                steps.append({
                    "step_type": "selection",
                    "description": f"询问玩家选择要丢弃的{count_desc}手牌",
                    "action": "wait_for_selection",
                    "params": {"source": "hand", "max_count": count if isinstance(count, int) else None, "min_count": count if isinstance(count, int) else 0},
                    "depends_on": [],
                    "optional": False
                })
                steps.append({
                    "step_type": "move",
                    "description": f"将玩家选择的{count_desc}卡牌从手牌移到弃牌堆",
                    "action": "move_cards",
                    "params": {"source": "hand", "target": "discard"},
                    "depends_on": [get_step_index(-1)],
                    "optional": False
                })
            else:
                # 从其他来源丢弃（如从宝可梦上丢弃能量）
                steps.append({
                    "step_type": "move",
                    "description": action.get("description", f"从{source}丢弃{count_desc}{card_type}"),
                    "action": "discard_from",
                    "params": {"source": source, "count": count, "card_type": card_type},
                    "depends_on": [],
                    "optional": action.get("optional", False)
                })
        
        elif action["type"] == "search":
            # 搜索操作已在前面处理，这里跳过
            pass
        
        elif action["type"] == "shuffle_into":
            # "shuffle X into deck" (如 Iono)
            if action.get("source") == "hand" and action.get("target") == "deck":
                steps.append({
                    "step_type": "move",
                    "description": "将手牌以随机的顺序放回到牌库的底部",
                    "action": "shuffle_hand_into_deck_bottom",
                    "params": {"both_players": action.get("both_players", False)},
                    "depends_on": [],
                    "optional": False
                })
        
        elif action["type"] == "shuffle":
            # 普通洗牌
            # 检查是否已经通过特殊逻辑处理过了（如Super Rod）
            if not super_rod_handled:
                steps.append({
                    "step_type": "shuffle",
                    "description": "牌库洗牌",
                    "action": "shuffle_deck",
                    "params": {},
                    "depends_on": [],
                    "optional": False
                })
        
        elif action["type"] == "draw":
            if "count" in action:
                steps.append({
                    "step_type": "draw",
                    "description": f"抽{action['count']}张牌",
                    "action": "draw_cards",
                    "params": {"count": action["count"]},
                    "depends_on": [],
                    "optional": False
                })
            elif "for_each" in action:
                # 根据条件抽牌（如 Iono）
                if "prize" in action["for_each"].lower():
                    if action.get("both_players"):
                        steps.append({
                            "step_type": "query",
                            "description": "查询双方剩余的奖赏卡数量",
                            "action": "query_prize_counts",
                            "params": {"both_players": True},
                            "depends_on": [],
                            "optional": False
                        })
                    steps.append({
                        "step_type": "draw",
                        "description": "根据剩余奖赏卡数量抽牌",
                        "action": "draw_cards_by_prizes",
                        "params": {"both_players": action.get("both_players", False)},
                        "depends_on": [get_step_index(-1)] if action.get("both_players") else [],
                        "optional": False
                    })
        
        elif action["type"] == "move_to_hand":
            # "Put X in play into your hand" (如 Professor Turo's Scenario)
            # 需要查询场上的宝可梦（包括战斗区和备战区）
            if not any(s.get("action") == "query_pokemon_in_play" for s in steps):
                steps.append({
                    "step_type": "query",
                    "description": "查询场上的宝可梦（战斗区或备战区）",
                    "action": "query_pokemon_in_play",
                    "params": {},
                    "depends_on": [],
                    "optional": False
                })
            if not any(s.get("action") == "wait_for_selection" and "pokemon" in str(s.get("description", "")).lower() for s in steps):
                steps.append({
                    "step_type": "selection",
                    "description": "询问玩家选择场上的宝可梦",
                    "action": "wait_for_selection",
                    "params": {"max_count": 1, "min_count": 1},
                    "depends_on": [get_step_index(-1)],
                    "optional": False
                })
            steps.append({
                "step_type": "move",
                "description": "将玩家选择的宝可梦移到手牌（丢弃所有附着的卡牌）",
                "action": "move_pokemon_to_hand",
                "params": {"discard_attached": action.get("discard_attached", True)},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
        
        elif action["type"] == "heal":
            # Heal damage (C-06)
            amount = action.get("amount", "all")
            target = action.get("target", "this Pokémon")
            steps.append({
                "step_type": "heal",
                "description": action.get("description", f"治疗{target}的伤害"),
                "action": "heal_damage",
                "params": {
                    "amount": amount,
                    "target": target
                },
                "depends_on": [],
                "optional": action.get("optional", False)
            })
        
        elif action["type"] == "move_damage_counters":
            # Move damage counters (C-08)
            count = action.get("count", "all")
            source = action.get("source", "")
            target = action.get("target", "")
            steps.append({
                "step_type": "move_damage_counters",
                "description": action.get("description", f"从{source}移动伤害计数器到{target}"),
                "action": "move_damage_counters",
                "params": {
                    "count": count,
                    "source": source,
                    "target": target
                },
                "depends_on": [],
                "optional": action.get("optional", False)
            })
        
        elif action["type"] == "move_energy":
            # Move Energy (C-10)
            count = action.get("count", 1)
            energy_type = action.get("energy_type")
            source = action.get("source", "")
            target = action.get("target", "")
            steps.append({
                "step_type": "move_energy",
                "description": action.get("description", f"从{source}移动能量到{target}"),
                "action": "move_energy",
                "params": {
                    "count": count,
                    "energy_type": energy_type,
                    "source": source,
                    "target": target
                },
                "depends_on": [],
                "optional": action.get("optional", False)
            })
        
        elif action["type"] == "devolve":
            # Devolve (C-13)
            target = action.get("target", "")
            method = action.get("method", "")
            steps.append({
                "step_type": "devolve",
                "description": action.get("description", f"退化{target}"),
                "action": "devolve_pokemon",
                "params": {
                    "target": target,
                    "method": method
                },
                "depends_on": [],
                "optional": action.get("optional", False)
            })
        
        elif action.get("before_damage"):
            # Handle "before doing damage" actions
            # These should be executed before damage calculation
            # Mark them with a special flag
            step_desc = action.get("description", "在造成伤害之前执行的效果")
            step_action = action.get("type", "unknown")
            steps.append({
                "step_type": step_action,
                "description": step_desc,
                "action": f"before_damage_{step_action}",
                "params": action.get("params", {}),
                "depends_on": [],
                "optional": action.get("optional", False),
                "before_damage": True  # Mark this step to execute before damage
            })
    
    # 检查基于奖赏卡的伤害修正（在攻击中）
    if "prize" in effect_text and ("damage" in effect_text or "more damage" in effect_text):
        prize_damage_match = re.search(r"(\d+)\s+more damage.*prize", effect_text)
        if prize_damage_match:
            # 需要在伤害计算前查询对手奖赏卡数量
            steps.append({
                "step_type": "query",
                "description": "查询对手已获得的奖赏卡数量",
                "action": "query_opponent_prize_count",
                "params": {},
                "depends_on": [],
                "optional": False
            })
    
    # 检查回合结束
    if "turn ends" in effect_text or "your turn ends" in effect_text:
        # 计算依赖：依赖于前面所有步骤
        # 如果已有步骤，依赖最后一个步骤的索引
        depends_on = []
        if steps:
            # 最后一个步骤的索引
            last_step_index = get_step_index(-1)
            depends_on = [last_step_index]
        elif plan.execution_steps:
            # 如果 steps 为空但 plan.execution_steps 不为空，依赖 plan 中最后一个步骤
            depends_on = [len(plan.execution_steps) - 1]
        
        steps.append({
            "step_type": "end_turn",
            "description": "回合结束",
            "action": "end_turn",
            "params": {},
            "depends_on": depends_on,
            "optional": False
        })
    
    # 检查丢弃Stadium（仅在非Stadium卡的效果中）
    # Stadium卡本身使用后应该留在场上，不应该丢弃
    if "discard" in effect_text and "stadium" in effect_text and plan.effect_type != "trainer":
        steps.append({
            "step_type": "check",
            "description": "检查场上是否存在Stadium",
            "action": "check_stadium_in_play",
            "params": {},
            "depends_on": [],
            "optional": True
        })
        steps.append({
            "step_type": "move",
            "description": "将Stadium卡移到弃牌堆",
            "action": "discard_stadium",
            "params": {},
                "depends_on": [get_step_index(-1)] if len(steps) > 0 else [],
            "optional": True,
            "skip_if": "no_stadium"
        })
    
    # Stadium卡特殊处理：使用后留在场上
    if plan.effect_subtype == "Stadium":
        # Stadium卡从手牌移到Stadium区域（如果已有其他Stadium，将其移到对应玩家的弃牌堆）
        steps.append({
            "step_type": "move",
            "description": "将Stadium卡从手牌移到Stadium区域",
            "action": "play_stadium",
            "params": {},
            "depends_on": [],
            "optional": False
        })
    
    # 检查切换到对手备战区（基于规则文本模式）
    if "switch" in effect_text_lower and "opponent" in effect_text_lower:
        steps.append({
            "step_type": "query",
            "description": "查询对手备战区的宝可梦",
            "action": "query_opponent_bench",
            "params": {},
            "depends_on": [],
            "optional": False
        })
        steps.append({
            "step_type": "selection",
            "description": "询问玩家选择对手备战区的宝可梦",
            "action": "wait_for_selection",
            "params": {"max_count": 1},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
        steps.append({
            "step_type": "move",
            "description": "将对手被选择的备战区宝可梦与战斗区宝可梦交换位置",
            "action": "switch_opponent_pokemon",
            "params": {},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
    
    # 检查切换自己的宝可梦（基于规则文本模式）
    if "switch" in effect_text_lower and "your active pokémon" in effect_text_lower and "benched pokémon" in effect_text_lower:
        if not any(s.get("action") == "query_bench" for s in steps):
            steps.append({
                "step_type": "query",
                "description": "查询玩家备战区的宝可梦",
                "action": "query_bench",
                "params": {},
                "depends_on": [],
                "optional": False
            })
        if not any(s.get("action") == "wait_for_selection" and "bench" in str(s.get("params", {})).lower() for s in steps):
            steps.append({
                "step_type": "selection",
                "description": "询问玩家的选择",
                "action": "wait_for_selection",
                "params": {"max_count": 1, "min_count": 1},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
        steps.append({
            "step_type": "move",
            "description": "将玩家选择的备战区宝可梦与当前战斗区宝可梦交换位置",
            "action": "switch_pokemon",
            "params": {},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
    
    # 处理 "Shuffle... from your discard pile into your deck" (如 Super Rod)
    # 但需要检查是否已经通过search action处理过了，避免重复
    if "from your discard pile" in effect_text_lower and "into your deck" in effect_text_lower and not super_rod_handled:
        # 如果还没有查询弃牌区的步骤，添加它
        if not any(s.get("action") == "query_discard_candidates" for s in steps):
            # 解析卡牌类型
            criteria = {}
            if "pokémon" in effect_text_lower or "pokemon" in effect_text_lower:
                criteria["card_type"] = "Pokemon"
            if "energy" in effect_text_lower:
                criteria["card_type"] = "Energy"
                if "basic energy" in effect_text_lower:
                    criteria["energy_type"] = "Basic Energy"
            
            steps.append({
                "step_type": "query",
                "description": "查询弃牌区中符合条件的卡牌",
                "action": "query_discard_candidates",
                "params": criteria,
                "depends_on": [],
                "optional": False
            })
        # 如果还没有选择步骤，添加它
        if not any(s.get("action") == "wait_for_selection" and "discard" in str(s.get("params", {})).lower() for s in steps):
            up_to_match = re.search(r"up to (\d+)", effect_text_lower)
            max_count = int(up_to_match.group(1)) if up_to_match else 3
            steps.append({
                "step_type": "selection",
                "description": f"询问玩家的选择（最多选择{max_count}张，任意组合）",
                "action": "wait_for_selection",
                "params": {"max_count": max_count, "min_count": 0},
            "depends_on": [get_step_index(-1)],
                "optional": True
            })
        # 添加移动步骤
        steps.append({
            "step_type": "move",
            "description": "将玩家选择的卡牌从弃牌区放回牌库",
            "action": "move_cards_from_discard_to_deck",
            "params": {"source": "discard", "target": "deck"},
            "depends_on": [get_step_index(-1)],
            "optional": True
        })
        # 添加洗牌步骤
        steps.append({
            "step_type": "shuffle",
            "description": "牌库洗牌",
            "action": "shuffle_deck",
            "params": {},
            "depends_on": [get_step_index(-1)],
            "optional": False
        })
    
    # 处理 "Choose 1 of your Basic Pokémon in play. If you have a Stage 2 card..." (如 Rare Candy)
    if "choose" in effect_text_lower and "basic pokémon" in effect_text_lower and "in play" in effect_text_lower:
        if "stage 2" in effect_text_lower and "evolve" in effect_text_lower:
            steps.append({
                "step_type": "selection",
                "description": "询问玩家选择Basic宝可梦",
                "action": "wait_for_selection",
                "params": {"card_type": "Pokemon", "stage": "Basic", "max_count": 1, "min_count": 1},
                "depends_on": [],
                "optional": False
            })
            steps.append({
                "step_type": "selection",
                "description": "询问玩家选择手牌中的Stage 2宝可梦",
                "action": "wait_for_selection",
                "params": {"source": "hand", "card_type": "Pokemon", "stage": "Stage 2", "max_count": 1, "min_count": 1},
                "depends_on": [],
                "optional": False
            })
            steps.append({
                "step_type": "move",
                "description": "将玩家选择的Stage 2宝可梦从手牌移到场上，替换Basic宝可梦",
                "action": "evolve_with_rare_candy",
                "params": {},
                "depends_on": [get_step_index(-2), get_step_index(-1)],
                "optional": False
            })
    
    # 处理 Tool 卡的附着逻辑
    # Tool卡需要附着到宝可梦上，而不是丢弃
    # 但只有在没有其他效果步骤时才添加附着逻辑（Tool卡可能只有被动效果）
    # 注意：这个检查需要在添加 discard_trainer 之前进行
    tool_has_effect_steps = False
    if plan.effect_type == "trainer" and plan.effect_subtype == "Tool":
        # 检查是否已经有其他效果步骤（排除后续会添加的 discard_trainer）
        # 如果有，说明Tool卡有主动效果，不需要额外添加附着步骤
        # 如果没有，说明Tool卡只有被动效果，需要添加附着步骤
        if not steps:
            # Tool卡只有被动效果，需要附着到宝可梦上
            steps.append({
                "step_type": "query",
                "description": "查询场上的宝可梦（战斗区或备战区）",
                "action": "query_pokemon_in_play",
                "params": {"exclude_tool_attached": True},  # 排除已有道具的宝可梦
                "depends_on": [],
                "optional": False
            })
            steps.append({
                "step_type": "selection",
                "description": "询问玩家选择要附着道具的宝可梦",
                "action": "wait_for_selection",
                "params": {"max_count": 1, "min_count": 1},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
            steps.append({
                "step_type": "attach",
                "description": "将道具卡附着到玩家选择的宝可梦上",
                "action": "attach_tool",
                "params": {"target": "pokemon"},
                "depends_on": [get_step_index(-1)],
                "optional": False
            })
        else:
            tool_has_effect_steps = True
    
    # 训练家卡使用后，除了Stadium和Tool，其他都应该移到弃牌堆
    # 这个步骤应该在所有其他步骤之后
    # 注意：Tool卡不应该被丢弃，它们会附着到宝可梦上
    if plan.effect_type == "trainer" and plan.effect_subtype not in ["Stadium", "Tool"]:
        # 计算依赖：依赖于最后一个步骤
        # 注意：如果steps为空，说明没有其他步骤，直接丢弃
        if steps:
            last_step_idx = get_step_index(-1) if len(steps) > 0 else base_step_index
            steps.append({
                "step_type": "move",
                "description": "将训练家卡移到弃牌堆",
                "action": "discard_trainer",
                "params": {},
                "depends_on": [last_step_idx],
                "optional": False
            })
        else:
            # 如果没有其他步骤，直接添加丢弃步骤
            steps.append({
                "step_type": "move",
                "description": "将训练家卡移到弃牌堆",
                "action": "discard_trainer",
                "params": {},
                "depends_on": [],
            "optional": False
        })
    
    # 在添加步骤之前，确保 before_damage 步骤在伤害步骤之前
    # 找到伤害步骤的索引
    damage_step_indices = []
    for i, step in enumerate(plan.execution_steps):
        if step.get("step_type") == "damage" or step.get("action") == "calculate_and_apply_damage":
            damage_step_indices.append(i)
    
    # 如果有 before_damage 步骤和伤害步骤，需要调整顺序
    before_damage_steps = [s for s in steps if s.get("before_damage")]
    regular_steps = [s for s in steps if not s.get("before_damage")]
    
    if before_damage_steps and damage_step_indices:
        # 将 before_damage 步骤插入到伤害步骤之前
        # 先添加 before_damage 步骤
        plan.execution_steps.extend(before_damage_steps)
        # 然后添加常规步骤
        plan.execution_steps.extend(regular_steps)
    else:
        # 正常添加所有步骤
        plan.execution_steps.extend(steps)


def _parse_damage_modifiers(effect_text: str, damage_calc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """解析伤害修正器
    
    Args:
        effect_text: 效果文本
        damage_calc: 从 RulePatternMatcher.parse_damage_calculation 返回的结果（可选）
    
    Returns:
        伤害修正器列表
    """
    import re
    modifiers = []
    
    # 如果提供了 damage_calc，优先使用它
    if damage_calc:
        calc_type = damage_calc.get("type")
        
        if calc_type == "damage_bonus_per":
            # "does N more damage for each X"
            modifiers.append({
                "type": "bonus_per",
                "bonus": damage_calc.get("bonus"),
                "condition": damage_calc.get("condition")
            })
        elif calc_type == "damage_bonus":
            # "does N more damage"
            modifiers.append({
                "type": "bonus",
                "bonus": damage_calc.get("bonus")
            })
        elif calc_type == "damage_to_self":
            # "This Pokémon does N damage to itself"
            modifiers.append({
                "type": "self_damage",
                "amount": damage_calc.get("damage")
            })
        elif calc_type == "damage_to_multiple":
            # "This attack does N damage (each) to X of your opponent's Pokémon"
            modifiers.append({
                "type": "damage_to_multiple",
                "damage": damage_calc.get("damage"),
                "count": damage_calc.get("count")
            })
        elif calc_type == "attack_does_nothing":
            # "The attack does nothing"
            modifiers.append({
                "type": "attack_does_nothing"
            })
    
    # 回退到原有的正则表达式解析（用于向后兼容）
    if not modifiers:
        # 检查基于奖赏卡的伤害修正
        prize_match = re.search(r"(\d+)\s+more damage.*prize", effect_text)
        if prize_match:
            modifiers.append({
                "type": "prize_based",
                "bonus_per_prize": int(prize_match.group(1))
            })
        
        # 检查自伤
        self_damage_match = re.search(r"does (\d+) damage to itself", effect_text)
        if self_damage_match:
            modifiers.append({
                "type": "self_damage",
                "amount": int(self_damage_match.group(1))
            })
    
    return modifiers


def _determine_target(rules_text: str) -> str:
    """根据rules_text确定目标区域"""
    if ("onto your bench" in rules_text or "put them onto your bench" in rules_text or
        "onto their bench" in rules_text or "put it onto their bench" in rules_text or
        "put them onto their bench" in rules_text):
        return "bench"
    elif "into your hand" in rules_text or "put it into your hand" in rules_text:
        return "hand"
    elif "onto the bench" in rules_text:
        return "bench"
    else:
        return "hand"  # 默认


def _analyze_restrictions(plan: CardExecutionPlan, card_def: CardDefinition) -> None:
    """分析使用限制"""
    rules_text = card_def.rules_text or ""
    rules_text_lower = rules_text.lower()
    
    restrictions = []
    
    # 检查回合限制
    if "first turn" in rules_text_lower or "only during your first turn" in rules_text_lower:
        restrictions.append({
            "type": "turn_limit",
            "value": 1,
            "condition": "first_turn"
        })
    
    # 检查玩家限制
    if "first player" in rules_text_lower and "cannot" in rules_text_lower:
        restrictions.append({
            "type": "player_limit",
            "condition": "first_player",
            "cannot_use": True
        })
    
    plan.restrictions = restrictions


def _query_rulebook_references(plan: CardExecutionPlan, rules_text: str, rulebook_query: RulebookQuery) -> None:
    """查询并添加相关规则文档引用。
    
    Args:
        plan: 卡牌执行预案
        rules_text: 规则文本
        rulebook_query: 规则文档查询器
    """
    if not rules_text or not rules_text.strip():
        return
    
    # 确保 rulebook_references 已初始化
    if plan.rulebook_references is None:
        plan.rulebook_references = []
    
    # 查询相关规则文档
    references = rulebook_query.query_by_text(rules_text)
    
    # 提取规则ID和摘要
    seen_rule_ids = set()
    for ref in references:
        rule_id = ref.get("rule_id")
        if rule_id and rule_id not in seen_rule_ids:
            seen_rule_ids.add(rule_id)
            
            # 获取规则摘要
            summary = rulebook_query.get_rule_summary(rule_id)
            
            # 确定匹配的模式类型
            pattern_type = None
            content_lower = ref.get("content", "").lower()
            if "heal" in content_lower:
                pattern_type = "heal"
            elif "move" in content_lower and "damage counter" in content_lower:
                pattern_type = "move_damage_counters"
            elif "move" in content_lower and "energy" in content_lower:
                pattern_type = "move_energy"
            elif "devolve" in content_lower:
                pattern_type = "devolve"
            elif "before doing damage" in content_lower:
                pattern_type = "before_doing_damage"
            elif "damage to itself" in content_lower:
                pattern_type = "damage_to_self"
            elif "damage" in content_lower and "each" in content_lower and "opponent" in content_lower:
                pattern_type = "damage_to_multiple"
            elif "does nothing" in content_lower:
                pattern_type = "attack_does_nothing"
            
            plan.rulebook_references.append({
                "rule_id": rule_id,
                "filename": ref.get("filename", ""),
                "summary": summary or "",
                "pattern_type": pattern_type
            })
    
    # 根据识别的模式类型查询额外的规则文档
    actions = RulePatternMatcher.parse_action_sequence(rules_text)
    for action in actions:
        action_type = action.get("type")
        if action_type:
            pattern_refs = rulebook_query.query_by_pattern(action_type)
            for ref in pattern_refs:
                rule_id = ref.get("rule_id")
                if rule_id and rule_id not in seen_rule_ids:
                    seen_rule_ids.add(rule_id)
                    summary = rulebook_query.get_rule_summary(rule_id)
                    plan.rulebook_references.append({
                        "rule_id": rule_id,
                        "filename": ref.get("filename", ""),
                        "summary": summary or "",
                        "pattern_type": action_type
                    })

