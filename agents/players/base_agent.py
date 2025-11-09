"""LangChain integration for Player Agent."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent
from src.ptcg_ai.referee import OperationRequest

from .tools import create_player_tools
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

logger = logging.getLogger(__name__)


class PlayerAgentSDK:
    """Player Agent with LangChain integration."""

    def __init__(
        self,
        base_agent: BasePlayerAgent,
        llm: BaseChatModel,
        strategy: str = "default",
        instructions: Optional[str] = None,
        knowledge_base: Optional[Any] = None,
        rulebook_query: Optional[RulebookQuery] = None,
    ):
        """Initialize Player Agent with LangChain.

        Args:
            base_agent: Base PlayerAgent instance
            llm: LangChain chat model (e.g., ChatOpenAI, ChatAnthropic)
            strategy: Strategy name for the player
            instructions: Custom instructions (optional)
            knowledge_base: RuleKnowledgeBase instance for querying rules (optional)
            rulebook_query: RulebookQuery instance for querying advanced-manual-split (optional)
        """
        self.base_agent = base_agent
        self.llm = llm
        self.strategy = strategy
        self.knowledge_base = knowledge_base
        self.rulebook_query = rulebook_query

        default_instructions = f"""
你是一个使用 {strategy} 策略的宝可梦集换式卡牌游戏（PTCG）玩家智能体。
你的目标是通过以下方式赢得游戏：
1. 遵守游戏规则
2. 根据当前游戏状态做出最优决策
3. 有效管理你的资源（卡牌、能量、奖赏卡）
4. 预测对手的行动
5. 根据游戏状态调整你的策略

**⚠️ 重要：你需要通过自然语言向规则Agent提出请求，而不是使用结构化工具。**

**如何生成自然语言请求：**

**步骤1：观察游戏状态并理解卡牌效果**
- 仔细查看观察信息中的 my_hand_cards、my_active_pokemon、my_bench_pokemon 等
- **⚠️ 重要：在决定使用任何卡牌之前，必须查看该卡牌的 "rules_text" 字段来理解卡牌效果和使用条件！**
- **⚠️ 关键：严格按照rules_text的原文理解，不要添加规则文本中没有的内容！**
- **⚠️ 必须查询规则书：在理解卡牌规则时，必须按以下顺序查询：**
  1. **首先使用 query_advanced_manual 工具查询 advanced-manual-split**：这是理解卡牌 rules、abilities、attacks 的最重要来源
     - 根据 rules_text 中的关键词（如 "heal", "discard", "switch", "attach energy" 等）查询相关规则文档
     - 根据 abilities 和 attacks 的效果文本查询相关规则文档
     - 这会帮助你深刻理解卡牌效果的具体含义和执行方式
  2. **然后使用 query_rule 工具查询 rulebook_extracted.txt**：用于理解基本游戏规则
     - **攻击规则**：只能使用战斗区的宝可梦进行攻击，不能使用手牌中的宝可梦攻击
     - **使用卡牌规则**：必须从手牌中使用卡牌，不能使用场上的卡牌
     - **其他基本规则**：如果不确定某个操作是否合法，必须先查询规则书
  - 如果规则文本说"up to 3"或"choose"，意味着玩家可以选择，不是随机
  - 如果规则文本没有提到"random"或"randomly"，就不要说"随机"
  - 如果规则文本没有提到"automatic"或"automatically"，就不要说"自动"
  - 不要添加规则文本中没有的词汇或概念
- 例如：如果卡牌是训练家卡，查看 "rules_text" 了解使用条件和效果
- 例如：如果卡牌是宝可梦，查看 "abilities" 和 "attacks" 了解能力和攻击效果
- 了解当前可用的资源和对手状态

**理解卡牌效果的示例：**
- Super Rod的规则文本是"Shuffle up to 3 in any combination of Pokémon and Basic Energy cards from your discard pile into your deck."
  - 正确理解：你可以从弃牌堆中选择最多3张宝可梦或基础能量卡洗回牌库（不是随机）
  - 错误理解：随机将最多3张卡洗回牌库 ❌（规则文本中没有"random"）
- 如果规则文本说"Search your deck for..."，这意味着你可以搜索并选择，不是随机抽取
- 如果规则文本说"Draw X cards"，这意味着抽X张牌（通常是随机的，但规则文本会明确说明）

**步骤2：决定要执行的操作**
- 根据游戏状态和卡牌效果，决定要执行什么操作
- **在决定使用卡牌前，必须确认满足卡牌的使用条件（查看 rules_text）**
- **⚠️ 攻击前的强制检查清单**（在决定攻击前必须完成）：
  1. **检查战斗区**：查看 my_active_pokemon 列表，确认战斗区有宝可梦
  2. **确认攻击来源**：只能使用 my_active_pokemon 中的宝可梦进行攻击
  3. **检查能量需求**：查看该宝可梦的 attacks 列表，确认有足够的能量
  4. **确认对手状态**：仔细查看 opponent_active_pokemon 列表，确认对手战斗区的宝可梦名称和 UID
  5. **查询规则**：如果不确定攻击规则，使用 query_rule("attack with active pokemon") 查询规则书
  6. **绝对禁止**：不能使用 my_hand_cards 或 my_bench_pokemon 中的宝可梦攻击

**步骤3：从观察信息中查找所需的UID和卡牌名称**
- 在 my_hand_cards、my_active_pokemon、my_bench_pokemon 等中找到相关卡牌
- 获取卡牌的 "uid" 字段和 "name" 字段
- **重要：必须使用 "uid" 字段，绝对不能只使用卡牌名称！**

**步骤4：生成自然语言请求**
- 使用以下格式生成自然语言请求，必须包含所有相关卡牌的 UID（格式：uid:xxxxx）
- **所有请求必须包含 UID，格式为 (uid:xxxxx)**

**自然语言请求格式示例：**

1. **附能操作**：
   "我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"

2. **使用训练家卡**：
   "我想使用手牌中的Iono(uid:playerA-deck-037)"
   "我想使用手牌中的Nest Ball(uid:playerA-deck-028)来搜索牌库中的基础宝可梦"

3. **放置宝可梦到备战区**：
   "我想将手牌中的Pikachu(uid:playerA-deck-017)放置到备战区"

4. **进化**：
   "我想将Charmander(uid:playerA-deck-015)进化为Charmeleon(uid:playerA-deck-016)"

5. **撤退/切换**：
   "我想将战斗区的Pikachu(uid:playerA-deck-015)撤退，切换到备战区的Raichu(uid:playerA-deck-017)"

6. **使用能力**：
   "我想使用Pikachu(uid:playerA-deck-015)的'Thunder Shock'能力"

7. **攻击**：
   **⚠️ 关键规则：只有战斗区的宝可梦可以发动攻击！**
   - **绝对禁止**：不能使用手牌中的宝可梦攻击
   - **绝对禁止**：不能使用备战区的宝可梦攻击
   - **只能使用**：my_active_pokemon 中的宝可梦进行攻击
   - 在决定攻击前，**必须检查 my_active_pokemon 列表**，确认战斗区有宝可梦
   - 攻击示例："我想使用Charizard(uid:playerA-deck-015)的'Blaze'攻击对手的Pikachu(uid:playerB-deck-020)"
   - **重要**：攻击时使用的宝可梦 UID 必须来自 my_active_pokemon，不能来自 my_hand_cards 或 my_bench_pokemon

8. **结束回合**：
   "我想结束回合" 或 "我不进行攻击"

9. **处理选择请求**（当Referee要求你选择卡牌时）：
   - 如果Referee返回了候选列表（candidates），说明需要你选择卡牌
   - 查看候选列表和选择要求（可能需要选择1张、最多2张、最多3张等）
   - 根据你的策略选择最合适的卡牌
   - 返回选择结果：
     * 选择1张：格式："我选择[卡牌名称](uid:xxxxx)"
     * 选择多张：格式："我选择[卡牌1](uid:xxxxx)和[卡牌2](uid:yyyyy)" 或 "我选择[卡牌1](uid:xxxxx)、[卡牌2](uid:yyyyy)"
   - 示例：
     * 选择1张：如果候选列表中有Pidgey(uid:playerA-deck-011)和Rotom V(uid:playerA-deck-013)，你选择Rotom V，则返回："我选择Rotom V(uid:playerA-deck-013)"
     * 选择2张（Battle VIP Pass）：如果可以选择最多2张，你选择Pidgey和Rotom V，则返回："我选择Pidgey(uid:playerA-deck-011)和Rotom V(uid:playerA-deck-013)"

**示例推理过程（使用 Nest Ball）：**
1. 观察：我看到 my_hand_cards 中有 {{"uid": "playerA-deck-028", "name": "Nest Ball", "type": "Trainer", "rules_text": "Search your deck for a Basic Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."}}
2. 理解效果：严格按照rules_text理解 - Nest Ball 的效果是搜索牌库中的基础宝可梦（你可以选择），揭示它，加入手牌，然后洗牌。规则文本说"Search"，意味着你可以选择，不是随机。
3. 决定：我想使用 Nest Ball
4. 查找信息：从 my_hand_cards 中找到 Nest Ball 的 uid 是 "playerA-deck-028"，name 是 "Nest Ball"
5. 生成请求："我想使用手牌中的Nest Ball(uid:playerA-deck-028)来搜索牌库中的基础宝可梦"

**示例推理过程（使用 Super Rod）：**
1. 观察：我看到 my_hand_cards 中有 {{"uid": "playerA-deck-040", "name": "Super Rod", "type": "Trainer", "rules_text": "Shuffle up to 3 in any combination of Pokémon and Basic Energy cards from your discard pile into your deck."}}
2. 理解效果：严格按照rules_text理解 - Super Rod 的效果是"Shuffle up to 3"，这意味着你可以从弃牌堆中选择最多3张宝可梦或基础能量卡洗回牌库。规则文本中没有"random"，所以不是随机，而是你可以选择。
3. 决定：我想使用 Super Rod，从弃牌堆中选择最多3张宝可梦或基础能量卡洗回牌库
4. 查找信息：从 my_hand_cards 中找到 Super Rod 的 uid 是 "playerA-deck-040"
5. 生成请求："我想使用手牌中的Super Rod(uid:playerA-deck-040)，从弃牌堆中选择最多3张宝可梦或基础能量卡洗回牌库"

**示例推理过程（附能操作）：**
1. 观察：我看到 my_hand_cards 中有能量卡 {{"uid": "playerA-deck-020", "name": "基础超能量"}}，战斗区有 {{"uid": "playerA-deck-015", "name": "Arceus V"}}
2. 决定：我想将能量附到 Arceus V 上
3. 查找信息：能量卡 uid: "playerA-deck-020"，宝可梦 uid: "playerA-deck-015"
4. 生成请求："我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"

在做出决策前，请仔细分析游戏状态。考虑以下因素：
- **你的手牌和牌库组成**
- **每张卡牌的效果文本（rules_text）和使用条件** - **这是最重要的！**
- **可用的宝可梦及其能力（abilities）和攻击（attacks）**
- **攻击所需的能量要求**
- **奖赏卡数量**
- **对手的场上状态（如果可见）**
- **卡牌的使用限制（例如：Lost Vacuum 需要先丢弃手牌到 Lost Zone）**

做出能够最大化获胜机会的决策。

在做出决策时：
1. 首先使用 analyze_game_state 来理解当前情况（可选）
2. 使用 remember 来存储重要的观察结果以供将来参考（可选）
3. **直接生成自然语言请求，描述你想要执行的操作**，或者明确说明"我想结束回合"

重要提示：
- **回合开始时会自动抽一张牌，这是规则强制的，你不需要也不能主动抽卡**
- **每个回合分为3个部分**：
  1. 抽一张牌（自动完成）
  2. 执行操作（可以按任意顺序，任意次数，除非有特殊限制）
  3. 攻击（可选，攻击后回合结束）
  
- **⚠️ 重要规则：先手玩家第一回合限制**
  - **先手玩家第一回合不能攻击**：如果观察信息显示 turn_number=1 且你是先手玩家（第一个玩家），**绝对不能尝试攻击**
  - **先手玩家第一回合不能使用Supporter卡**：如果观察信息显示 turn_number=1 且你是先手玩家，**不能使用Supporter卡**
  - 在决定攻击或使用Supporter卡前，**必须检查观察信息中的 turn_number**
  - 如果 turn_number=1 且你是先手玩家，应该执行其他操作（如附能、放置宝可梦、使用Item卡等），或者直接结束回合
- **操作限制**：
  - 附能：每回合只能一次
  - 撤退：每回合只能一次
  - Supporter卡：每回合只能使用一张（**先手玩家第一回合不能使用**）
  - Stadium卡：每回合只能使用一张
  - 其他操作（放置宝可梦、进化、使用能力、使用Item卡）：可以任意次数
  - **攻击：先手玩家第一回合不能攻击** ⚠️ **重要规则！**
- 你必须通过自然语言请求来描述你想要执行的操作
- 如果你想结束回合而不攻击，直接说明"我想结束回合"即可
- **观察信息结构说明**：
  * my_hand_cards: 你的手牌列表（包含uid、name、type、rules_text、abilities、attacks等信息）
    - **rules_text**: 卡牌效果文本，**必须查看此字段来理解卡牌效果和使用条件！**
    - **abilities**: 宝可梦的能力列表（如果有）
    - **attacks**: 宝可梦的攻击列表（如果有）
  * my_active_pokemon: 你的战斗区宝可梦（包含uid、hp、伤害、附能、abilities、attacks等信息）
    - **⚠️ 重要：只有 my_active_pokemon 中的宝可梦可以发动攻击！**
    - 如果 my_active_pokemon 为空列表 []，说明战斗区没有宝可梦，不能攻击
    - 攻击时使用的宝可梦 UID 必须来自 my_active_pokemon
  * my_bench_pokemon: 你的备战区宝可梦（包含uid、hp、伤害、附能、abilities、attacks等信息）
    - **⚠️ 重要：备战区的宝可梦不能直接攻击，必须先切换到战斗区**
  * my_discard_pile: 你的弃牌区（最近10张）
  * opponent_hand_size: 对手手牌数量
  * opponent_active_pokemon: 对手战斗区宝可梦（包含uid、name、hp、伤害、abilities、attacks等信息）
    - **⚠️ 重要：在决定攻击目标前，必须仔细查看 opponent_active_pokemon 列表**
    - 确认对手战斗区宝可梦的 name 和 uid，不要猜测或假设
    - 如果 opponent_active_pokemon 为空列表 []，说明对手战斗区没有宝可梦
  * opponent_bench_pokemon: 对手备战区宝可梦（包含uid、name、hp、伤害、abilities、attacks等信息）
  * opponent_discard_pile: 对手弃牌区（最近10张）
  * my_deck_size / opponent_deck_size: 双方牌库剩余数量
  * my_prizes / opponent_prizes: 双方剩余奖赏卡数量

- **⚠️ 使用卡牌时，必须使用卡牌的 UID（在观察信息的 uid 字段中），绝对不能使用卡牌名称！**
- 例如：如果my_hand_cards中有{{"uid": "arven-001", "name": "Arven"}}，要使用这张卡时，必须使用"arven-001"作为card_id，不能使用"Arven"
- 在决定使用哪张卡之前，请仔细查看观察信息中的my_hand_cards列表，找到对应的uid字段
- 所有宝可梦（战斗区、备战区）都有uid字段，使用能力或攻击时也需要使用uid
- **⚠️ 攻击时的UID使用规则**：
  - 攻击时使用的宝可梦 UID 必须来自 my_active_pokemon（战斗区）
  - 攻击目标（如果有）的 UID 必须来自 opponent_active_pokemon 或 opponent_bench_pokemon
  - **绝对禁止**：不能使用 my_hand_cards 中的宝可梦 UID 进行攻击
  - **绝对禁止**：不能使用 my_bench_pokemon 中的宝可梦 UID 进行攻击（除非先切换到战斗区）
- **如果观察信息中包含 last_action_error 字段，说明上一次操作失败了。请仔细阅读错误消息，并根据错误提示修正你的操作。**
- 常见错误：
  * 如果错误提到"Invalid parameter name 'trainer_card'"，说明你使用了错误的参数名，应该使用"card_id"
  * 如果错误提到"you used the card name"，说明你使用了卡牌名称而不是UID，请从hand_cards中查找对应的uid字段
  * 如果错误提到"not found in hand"，说明你使用的UID不存在，请检查hand_cards列表
  * 如果错误提到"not in active"或"not in battle"，说明你尝试使用非战斗区的宝可梦攻击，必须使用 my_active_pokemon 中的宝可梦
  * 如果错误提到"wrong opponent pokemon"，说明你识别错了对手的宝可梦，请仔细查看 opponent_active_pokemon 列表中的 name 和 uid

**⚠️ 攻击操作的完整检查流程**（必须严格执行）：
1. **检查战斗区**：查看 my_active_pokemon 列表
   - 如果为空 []，不能攻击，必须先放置宝可梦到战斗区
   - 如果不为空，记录战斗区宝可梦的 name 和 uid
2. **检查能量**：查看 my_active_pokemon[0] 的 attacks 列表和 attached_energy_count
   - 确认有足够的能量来发动攻击
3. **检查对手状态**：查看 opponent_active_pokemon 列表
   - 仔细查看 name 字段，确认对手战斗区宝可梦的名称（例如：如果是 "Charmander"，不要误认为是 "Blastoise"）
   - 记录对手战斗区宝可梦的 uid（如果需要指定攻击目标）
4. **查询规则**：如果不确定，使用 query_rule("attack with active pokemon") 查询规则书
5. **生成请求**：使用 my_active_pokemon 中的宝可梦 UID 和 opponent_active_pokemon 中的目标 UID（如果需要）
"""
        self.instructions = instructions or default_instructions

        # Create tools
        self.tools = create_player_tools(base_agent, knowledge_base=knowledge_base, rulebook_query=rulebook_query)

        # Create agent using LangChain 1.0 API
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.instructions,
        )

    def invoke(self, observation: Dict[str, Any], return_reasoning: bool = False) -> tuple[Optional[str], Optional[list]]:
        """Make a decision based on game observation using LangChain agent.
        
        现在返回自然语言请求字符串，而不是 OperationRequest。

        Args:
            observation: Current game state observation
            return_reasoning: If True, also return the reasoning messages

        Returns:
            Tuple of (自然语言请求字符串 if action is decided, None if ending turn, reasoning messages if return_reasoning=True)
        """
        # 打印观察信息摘要用于调试
        logger.info(f"[PlayerAgentSDK] 收到观察信息:")
        logger.info(f"  - 手牌数量: {len(observation.get('my_hand_cards', []))}")
        logger.info(f"  - 战斗区宝可梦: {len(observation.get('my_active_pokemon', []))}")
        logger.info(f"  - 备战区宝可梦: {len(observation.get('my_bench_pokemon', []))}")
        logger.info(f"  - 回合数: {observation.get('turn_number', 'unknown')}")
        if observation.get('my_hand_cards'):
            hand_names = [card.get('name', 'unknown') for card in observation.get('my_hand_cards', [])[:5]]
            logger.info(f"  - 手牌前5张: {hand_names}")
        
        # Format the observation as input
        input_text = f"当前游戏状态观察: {json.dumps(observation, default=str, ensure_ascii=False)}"
        logger.info(f"[PlayerAgentSDK] 输入文本长度: {len(input_text)} 字符")

        try:
            # LangChain 1.0 API: agent is a graph, invoke with messages
            logger.info(f"[PlayerAgentSDK] 调用 agent.invoke...")
            result = self.agent.invoke({"messages": [{"role": "user", "content": input_text}]})
            logger.info(f"[PlayerAgentSDK] agent.invoke 返回，类型: {type(result)}")
            
            # Extract the response from the result
            messages = []
            if isinstance(result, dict):
                if "messages" in result:
                    messages = result["messages"]
                else:
                    messages = [result]
            elif hasattr(result, "messages"):
                messages = result.messages
            else:
                messages = [result]
            
            logger.info(f"[PlayerAgentSDK] 提取到 {len(messages)} 条消息")
            
            # Store reasoning for debugging
            reasoning_messages = messages if return_reasoning else None
            
            # 打印所有消息的摘要用于调试
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                if hasattr(msg, "content") and msg.content:
                    content_preview = str(msg.content)[:200]
                    logger.info(f"[PlayerAgentSDK] 消息[{i}] ({msg_type}): {content_preview}...")
                elif hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_names = [getattr(tc, 'name', 'unknown') if hasattr(tc, 'name') else (tc.get('name', 'unknown') if isinstance(tc, dict) else 'unknown') for tc in msg.tool_calls]
                    logger.info(f"[PlayerAgentSDK] 消息[{i}] ({msg_type}): 工具调用 - {tool_names}")
                else:
                    logger.info(f"[PlayerAgentSDK] 消息[{i}] ({msg_type}): {str(msg)[:200]}")
            
            # Extract natural language request from the last AI message
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    content = str(msg.content).strip()
                    
                    # Skip empty content or tool call messages
                    if not content or content.startswith("Tool calls:"):
                        continue
                    
                    # Check if it's an end turn request
                    if "结束回合" in content or "不进行攻击" in content or "end turn" in content.lower():
                        logger.info("AI 决定结束回合")
                        if return_reasoning:
                            return None, reasoning_messages
                        return None, None
                    
                    # Check if it contains a natural language request (should contain "uid:" or be a clear action description)
                    # Look for patterns like "我想..." or "I want to..." or contains "uid:"
                    if "我想" in content or "I want" in content.lower() or "uid:" in content:
                        logger.info(f"AI 生成自然语言请求: {content}")
                        if return_reasoning:
                            return content, reasoning_messages
                        return content, None
                    
                    # If the message doesn't look like a request, try to extract it
                    # Look for quoted strings or action descriptions
                    import re
                    # Try to find quoted request
                    quoted_match = re.search(r'["\']([^"\']+)["\']', content)
                    if quoted_match:
                        request_text = quoted_match.group(1)
                        if "uid:" in request_text or "我想" in request_text:
                            logger.info(f"AI 生成自然语言请求 (从引号中提取): {request_text}")
                            if return_reasoning:
                                return request_text, reasoning_messages
                            return request_text, None
                    
                    # If content looks like a natural language request, use it
                    if len(content) > 10 and ("使用" in content or "附" in content or "放置" in content or 
                                              "进化" in content or "撤退" in content or "攻击" in content):
                        logger.info(f"AI 生成自然语言请求: {content}")
                        if return_reasoning:
                            return content, reasoning_messages
                        return content, None
            
            # If no clear request found, check if agent wants to end turn
            logger.warning(f"[PlayerAgentSDK] ⚠️ AI 决定结束回合（未找到有效操作）")
            logger.warning(f"[PlayerAgentSDK] 最后一条消息内容: {str(messages[-1]) if messages else '无消息'}")
            if return_reasoning:
                return None, reasoning_messages
            return None, None
            
        except Exception as e:
            logger.error(f"做出决策时出错: {e}", exc_info=True)
            import traceback
            logger.error(traceback.format_exc())
            # Fallback: return None to end turn
            if return_reasoning:
                return None, None
            return None, None

    def stream(self, observation: Dict[str, Any]):
        """Make a decision with streaming response.

        Args:
            observation: Current game state observation

        Yields:
            Chunks of the agent's response
        """
        input_text = f"当前游戏状态观察: {json.dumps(observation, default=str)}"

        try:
            # LangChain 1.0 API: stream with messages
            for chunk in self.agent.stream({"messages": [{"role": "user", "content": input_text}]}):
                yield chunk
        except Exception as e:
            logger.error(f"流式传输决策时出错: {e}", exc_info=True)
            yield {"error": str(e)}

    def _parse_action_from_response(self, response_text: str, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse action from agent response.

        The agent should use the decide_action tool, but we also try to parse from text
        as a fallback.

        Args:
            response_text: Agent response text
            observation: Current observation

        Returns:
            Action request dict or None
        """
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', response_text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if "action" in parsed:
                    return OperationRequest(
                        actor_id=self.base_agent.player_id,
                        action=parsed["action"],
                        payload=parsed.get("payload", {}),
                    )
            except json.JSONDecodeError:
                pass

        # Don't fallback to draw - if tool wasn't called, return None
        # This prevents incorrect actions from being executed
        logger.warning(f"Could not parse action from response text: {response_text[:200]}")
        return None
