"""LangChain tools for Player Agent."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent
from src.ptcg_ai.rulebook import RuleKnowledgeBase
# 直接导入 rulebook_query 模块，避免触发 __init__.py 的导入
import importlib.util
import sys
from pathlib import Path

# 直接加载 rulebook_query 模块，不通过 __init__.py
_rulebook_query_path = Path(__file__).parent.parent / "rule_analyst" / "rulebook_query.py"
_spec = importlib.util.spec_from_file_location("rulebook_query", _rulebook_query_path)
_rulebook_query_module = importlib.util.module_from_spec(_spec)
sys.modules["rulebook_query"] = _rulebook_query_module
_spec.loader.exec_module(_rulebook_query_module)
RulebookQuery = _rulebook_query_module.RulebookQuery


class AnalyzeGameStateInput(BaseModel):
    """Input schema for analyze_game_state tool."""

    observation: Dict[str, Any] = Field(description="当前游戏状态观察")


class DecideActionInput(BaseModel):
    """Input schema for decide_action tool."""

    action: str = Field(description="行动类型（draw, play_card, attack 等）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动特定的参数（必须是字典对象，不能是None。即使没有参数也要传递空字典{}）")
    
    @field_validator('payload', mode='before')
    @classmethod
    def validate_payload(cls, v):
        """将 None 转换为空字典，确保 payload 始终是字典对象"""
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError(f"payload must be a dictionary, got {type(v)}")
        return v


class RememberInput(BaseModel):
    """Input schema for remember tool."""

    content: str = Field(description="要存储的记忆内容")


def create_player_tools(base_agent: BasePlayerAgent, knowledge_base: Optional[RuleKnowledgeBase] = None, rulebook_query: Optional[RulebookQuery] = None) -> list[StructuredTool]:
    """Create LangChain tools for the player agent.

    Args:
        base_agent: Base PlayerAgent instance

    Returns:
        List of StructuredTool instances
    """
    def analyze_game_state(observation: Dict[str, Any]) -> str:
        """分析当前游戏状态以辅助决策制定。"""
        analysis = {
            "hand_size": observation.get("hand_size", 0),
            "prizes": observation.get("prizes", 6),
            "memory_count": len(base_agent.memory.thoughts),
            "observation": observation,
        }
        return json.dumps(analysis)

    def decide_action(action: str, payload: Optional[Dict[str, Any]] = None) -> str:
        """决定下一步要采取的行动。
        
        如果payload为None或缺失必需参数，会返回错误提示，告诉AI如何正确构造payload。
        """
        # 处理payload为None的情况
        if payload is None:
            payload = {}
        
        # 根据action类型，检查必需的参数
        required_params = {
            "play_trainer": ["card_id"],
            "move_to_bench": ["card_id"],
            "attach_energy": ["energy_card_id", "pokemon_id"],
            "evolve_pokemon": ["base_card_id", "evolution_card_id"],
            "switch_pokemon": ["bench_card_id"],
            "use_ability": ["card_id", "ability_name"],
            "use_attack": ["card_id", "attack_name"],
        }
        
        if action in required_params:
            missing = [p for p in required_params[action] if p not in payload or payload.get(p) is None or payload.get(p) == ""]
            if missing:
                # 生成详细的错误提示
                error_msg = {
                    "error": True,
                    "message": f"Action '{action}' requires the following parameters in payload: {missing}",
                    "action": action,
                    "missing_parameters": missing,
                    "hint": f"For '{action}', you must provide a payload dictionary with these required keys: {missing}",
                    "how_to_fix": _get_how_to_fix_hint(action, missing),
                    "example": _get_example_payload(action)
                }
                return json.dumps(error_msg, ensure_ascii=False)
        
        return json.dumps({
            "action": action,
            "payload": payload,
        })

    def _get_how_to_fix_hint(action: str, missing_params: list) -> str:
        """返回如何修复的提示"""
        hints = {
            "play_trainer": {
                "card_id": "1. 查看观察信息中的 my_hand_cards 列表\n2. 找到你想使用的训练家卡\n3. 复制该卡牌的 'uid' 字段值（不是 'name' 字段！）\n4. 使用: payload={\"card_id\": \"从my_hand_cards中找到的uid\"}"
            },
            "move_to_bench": {
                "card_id": "1. 查看观察信息中的 my_hand_cards 列表\n2. 找到基础宝可梦（stage为'Basic'）\n3. 复制该卡牌的 'uid' 字段值\n4. 使用: payload={\"card_id\": \"从my_hand_cards中找到的uid\"}"
            },
            "attach_energy": {
                "energy_card_id": "从 my_hand_cards 中找到能量卡的 uid",
                "pokemon_id": "从 my_active_pokemon 或 my_bench_pokemon 中找到宝可梦的 uid"
            },
            "evolve_pokemon": {
                "base_card_id": "从 my_active_pokemon 或 my_bench_pokemon 中找到要进化的宝可梦的 uid",
                "evolution_card_id": "从 my_hand_cards 中找到进化卡的 uid"
            },
            "switch_pokemon": {
                "bench_card_id": "从 my_bench_pokemon 中找到要切换的宝可梦的 uid"
            },
            "use_ability": {
                "card_id": "从 my_active_pokemon 或 my_bench_pokemon 中找到宝可梦的 uid",
                "ability_name": "从该宝可梦的 abilities 列表中找到能力名称"
            },
            "use_attack": {
                "card_id": "从 my_active_pokemon 中找到宝可梦的 uid",
                "attack_name": "从该宝可梦的 attacks 列表中找到攻击名称"
            }
        }
        
        action_hints = hints.get(action, {})
        return "\n".join([action_hints.get(p, f"需要提供参数: {p}") for p in missing_params])

    def _get_example_payload(action: str) -> Dict[str, str]:
        """返回示例payload，帮助AI理解如何构造参数"""
        examples = {
            "play_trainer": {
                "card_id": "playerA-deck-035",
                "note": "这是从 my_hand_cards 中找到的 uid，不是卡牌名称！"
            },
            "move_to_bench": {
                "card_id": "playerA-deck-015"
            },
            "attach_energy": {
                "energy_card_id": "playerA-deck-020",
                "pokemon_id": "playerA-deck-015"
            },
            "evolve_pokemon": {
                "base_card_id": "playerA-deck-015",
                "evolution_card_id": "playerA-deck-016"
            },
            "switch_pokemon": {
                "bench_card_id": "playerA-deck-017"
            },
            "use_ability": {
                "card_id": "playerA-deck-015",
                "ability_name": "Ability Name"
            },
            "use_attack": {
                "card_id": "playerA-deck-015",
                "attack_name": "Attack Name"
            }
        }
        return examples.get(action, {})

    def remember(content: str) -> str:
        """存储关于游戏的记忆以供将来参考。"""
        base_agent.memory.remember(content)
        return json.dumps({"success": True, "message": "记忆已存储"})

    analyze_game_state_tool = StructuredTool.from_function(
        func=analyze_game_state,
        name="analyze_game_state",
        description="分析当前游戏状态以辅助决策制定。返回包括手牌数量、奖赏卡数量和记忆数量的分析结果。",
        args_schema=AnalyzeGameStateInput,
    )

    decide_action_tool = StructuredTool.from_function(
        func=decide_action,
        name="decide_action",
        description="""决定下一步要采取的行动。这是你做出决策的主要工具。

**⚠️ 关键要求：payload 参数必须是一个字典对象（dict），绝对不能是 None 或 null！**

**⚠️ 重要：每次调用此工具时，必须提供 payload 参数，即使它是空字典 {{}}！**

**构造 payload 的步骤（以 play_trainer 为例）：**
1. 查看观察信息中的 my_hand_cards 列表
2. 找到你想使用的训练家卡（例如找到 name="Iono" 的卡）
3. **复制该卡牌的 "uid" 字段值**（例如 "playerA-deck-037"），**绝对不要使用 "name" 字段！**
4. 构造 payload 字典：{{"card_id": "playerA-deck-037"}}
5. 调用工具时，使用位置参数格式：decide_action("play_trainer", {{"card_id": "playerA-deck-037"}})

**⚠️ 工具调用格式（JSON Schema）：**
当你调用此工具时，必须使用以下格式：
{{
  "action": "play_trainer",
  "payload": {{
    "card_id": "playerA-deck-037"
  }}
}}

**绝对不要这样做：**
- {{"action": "play_trainer", "payload": null}}  ❌
- {{"action": "play_trainer"}}  ❌ (缺少payload)

**常见错误（不要这样做）：**
- payload=None  ❌
- payload=null  ❌  
- payload={{"card_id": "Iono"}}  ❌ 使用了名称而不是uid

**正确示例：**
- payload={{"card_id": "playerA-deck-037"}}  ✅ 使用了uid

**错误示例（不要这样做）：**
- decide_action("play_trainer", None)  ❌ payload不能是None
- decide_action("play_trainer")  ❌ 必须提供payload参数
- decide_action("play_trainer", {{"card_id": "Boss's Orders (Ghetsis)"}})  ❌ 使用了名称而不是uid

**正确示例：**
- decide_action("play_trainer", {{"card_id": "playerA-deck-035"}})  ✅ 使用了uid

重要提示：回合开始时会自动抽一张牌，这是规则强制的，你不需要也不能主动抽卡。

根据PTCG规则，每个回合分为3个部分：
1. 抽一张牌（自动完成）
2. 执行以下操作（可以按任意顺序，任意次数，除非有特殊限制）：
3. 攻击（可选，攻击后回合结束）

**⚠️ 重要：所有操作都必须使用卡牌的UID（在观察信息的uid字段中），不能使用卡牌名称！**

观察信息包含：
- my_hand_cards: 你的手牌（包含uid字段）
- my_active_pokemon: 你的战斗区宝可梦（包含uid字段）
- my_bench_pokemon: 你的备战区宝可梦（包含uid字段）
- opponent_active_pokemon: 对手战斗区宝可梦（包含uid字段）
- opponent_bench_pokemon: 对手备战区宝可梦（包含uid字段）
- 双方的手牌数量、牌库数量、奖赏卡数量、弃牌区信息等

可用的行动类型包括（按规则书顺序）：

A. "move_to_bench": 将手牌中的基础宝可梦放置到备战区
   - 可以执行任意次数
   - payload: {{"card_id": "基础宝可梦卡牌UID（必须从观察信息my_hand_cards中查找对应的uid字段）"}}
   - 注意：备战区最多只能有5张宝可梦
   - 示例: 如果手牌中有{{"uid": "charmander-001", "name": "Charmander"}}，则使用{{"card_id": "charmander-001"}}

B. "evolve_pokemon": 进化宝可梦
   - 可以执行任意次数
   - payload: {{"base_card_id": "要进化的宝可梦UID（必须在战斗区或备战区）", "evolution_card_id": "进化卡UID（必须在手牌中）", "skip_stage1": false（可选，使用Rare Candy时为true）}}
   - 示例: {{"base_card_id": "charmander-001", "evolution_card_id": "charmeleon-002"}}
   - 注意：宝可梦在场上第一回合不能进化，除非使用Rare Candy
   - 进化链：Basic -> Stage 1 -> Stage 2（使用Rare Candy可以跳过Stage 1）

C. "attach_energy": 将能量卡附到宝可梦上
   - 每回合只能执行一次
   - payload: {{"energy_card_id": "能量卡UID（必须从观察信息my_hand_cards中查找）", "pokemon_id": "宝可梦UID（从my_active_pokemon或my_bench_pokemon中查找）"}}
   - 示例: {{"energy_card_id": "fire-energy-001", "pokemon_id": "charmander-001"}}

D. "play_trainer": 使用训练家卡
   - Item卡和Pokémon Tool卡：可以执行任意次数
   - Supporter卡：每回合只能使用一张（先手玩家第一回合不能使用）
   - Stadium卡：每回合只能使用一张
   - **重要：必须使用卡牌的UID，不能使用卡牌名称！**
   - **payload 格式（必须）：** {{"card_id": "训练家卡UID"}}
   - **如何获取UID：** 在观察信息的 my_hand_cards 列表中，找到你想使用的训练家卡，复制它的 "uid" 字段值
   - **完整示例：** 
     * 观察信息中有：{{"uid": "playerA-deck-037", "name": "Iono", "type": "Trainer"}}
     * 正确的调用：decide_action(action="play_trainer", payload={{"card_id": "playerA-deck-037"}})
   - **错误示例：**
     * payload=None  ❌
     * payload={{"card_id": "Iono"}}  ❌ 使用了名称
     * payload={{"trainer_card": "Iono"}}  ❌ 错误的参数名

E. "switch_pokemon" (Retreat): 撤退战斗区宝可梦
   - 每回合只能执行一次
   - 需要支付撤退费用（丢弃相应数量的能量）
   - payload: {{"bench_card_id": "备战区宝可梦UID"}}
   - 注意：睡眠或麻痹状态的宝可梦不能撤退

F. "use_ability": 使用宝可梦能力
   - **重要：只能用于主动能力，不能用于被动能力！**
   - **主动能力**：包含"Once during your turn"、"You may"、"Search"、"Draw"等关键词
   - **被动能力**：包含"Prevent"、"As long as"、"Whenever"等关键词，一直生效，不需要也不能使用
   - 可以执行任意次数（每个主动能力可能有自己的使用限制）
   - payload: {{"card_id": "宝可梦UID（战斗区或备战区）", "ability_name": "能力名称"}}
   - **错误示例**：尝试使用被动能力（如Jirachi的"Stellar Veil"）会失败
   - **正确示例**：只使用主动能力（如"Once during your turn, you may search your deck..."）

3. "use_attack": 使用宝可梦攻击（攻击后回合结束）
   - 可选，如果攻击则回合结束
   - 需要检查能量需求
   - payload: {{"card_id": "战斗区宝可梦UID", "attack_name": "攻击名称", "target_pokemon_id": "目标宝可梦UID（可选）"}}
   - 注意：先手玩家第一回合不能攻击

如果你想结束回合而不攻击，不要调用此工具，直接说明"我想结束回合"即可。""",
        args_schema=DecideActionInput,
    )

    remember_tool = StructuredTool.from_function(
        func=remember,
        name="remember",
        description="存储关于游戏的记忆以供将来参考。使用此工具来记住重要的游戏事件或策略。",
        args_schema=RememberInput,
    )

    tools = [analyze_game_state_tool, decide_action_tool, remember_tool]
    
    # 如果提供了 rulebook_query，添加 query_advanced_manual 工具
    if rulebook_query:
        class QueryAdvancedManualInput(BaseModel):
            rules_text: str = Field(description="卡牌的规则文本（rules_text）、能力文本（abilities）或攻击文本（attacks），用于查询相关规则文档")
        
        def query_advanced_manual(rules_text: str) -> str:
            """在 advanced-manual-split 规则文档中查询相关规则。
            
            ⚠️ 重要：在理解卡牌规则时，必须首先使用此工具查询 advanced-manual-split！
            
            此工具会根据规则文本中的关键词（如 "heal", "discard", "switch", "attach energy" 等）
            自动匹配并返回相关的规则文档，帮助你深刻理解卡牌效果的具体含义和执行方式。
            
            使用方法：
            - 传入卡牌的 rules_text（训练家卡的效果文本）
            - 传入 abilities 中的效果文本（宝可梦能力）
            - 传入 attacks 中的效果文本（宝可梦攻击）
            
            工具会自动识别关键词并返回相关的规则文档。
            """
            import json
            results = rulebook_query.query_by_text(rules_text)
            # 格式化返回结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "filename": result.get("filename", "unknown"),
                    "rule_id": result.get("rule_id", "unknown"),
                    "content": result.get("content", "")[:2000]  # 限制内容长度
                })
            return json.dumps(formatted_results, ensure_ascii=False)
        
        query_advanced_manual_tool = StructuredTool.from_function(
            func=query_advanced_manual,
            name="query_advanced_manual",
            description="""在 advanced-manual-split 规则文档中查询相关规则。

⚠️ 重要：在理解卡牌规则时，必须首先使用此工具查询 advanced-manual-split！

这是理解卡牌的 rules、abilities、attacks 的最重要来源。

使用方法：
- 传入卡牌的 rules_text（训练家卡的效果文本）
- 传入 abilities 中的效果文本（宝可梦能力）
- 传入 attacks 中的效果文本（宝可梦攻击）

工具会自动识别规则文本中的关键词（如 "heal", "discard", "switch", "attach energy", "before doing damage" 等）
并返回相关的规则文档，帮助你深刻理解卡牌效果的具体含义和执行方式。

示例：
- query_advanced_manual("Heal 30 damage from 1 of your Pokémon") - 查询治疗规则
- query_advanced_manual("Discard 2 cards from your hand") - 查询丢弃规则
- query_advanced_manual("Switch your Active Pokémon with 1 of your Benched Pokémon") - 查询切换规则
- query_advanced_manual("Before doing damage, discard all Energy from this Pokémon") - 查询"before doing damage"规则""",
            args_schema=QueryAdvancedManualInput,
        )
        tools.append(query_advanced_manual_tool)
    
    # 如果提供了 knowledge_base，添加 query_rule 工具
    if knowledge_base:
        class QueryRuleInput(BaseModel):
            query: str = Field(description="要查询的规则关键词或问题")
            limit: int = Field(default=5, description="返回结果的最大数量")
        
        def query_rule(query: str, limit: int = 5) -> str:
            """在规则知识库（rulebook_extracted.txt）中查询相关规则。
            
            ⚠️ 重要：在决定任何操作之前，必须使用此工具查询规则书来理解游戏规则！
            特别是：
            - 攻击规则：只能使用战斗区的宝可梦进行攻击，不能使用手牌中的宝可梦
            - 使用卡牌规则：必须从手牌中使用卡牌
            - 其他基本规则：如果不确定某个操作是否合法，必须先查询规则书
            """
            import json
            matches = knowledge_base.find(query, limit=limit)
            results = [{"section": m.section, "text": m.text} for m in matches]
            return json.dumps(results, ensure_ascii=False)
        
        query_rule_tool = StructuredTool.from_function(
            func=query_rule,
            name="query_rule",
            description="""在规则知识库（rulebook_extracted.txt）中查询相关规则。

⚠️ 重要：在决定任何操作之前，必须使用此工具查询规则书来理解游戏规则！

特别是以下情况必须查询：
- **攻击规则**：只能使用战斗区的宝可梦进行攻击，不能使用手牌中的宝可梦攻击
- **使用卡牌规则**：必须从手牌中使用卡牌，不能使用场上的卡牌
- **其他基本规则**：如果不确定某个操作是否合法，必须先查询规则书

查询示例：
- query_rule("attack with pokemon in hand") - 查询是否可以用手牌中的宝可梦攻击
- query_rule("use card from hand") - 查询使用卡牌的规则
- query_rule("retreat pokemon") - 查询撤退规则""",
            args_schema=QueryRuleInput,
        )
        tools.append(query_rule_tool)
    
    return tools

