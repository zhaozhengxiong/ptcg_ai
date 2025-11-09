"""LangChain integration for Referee Agent."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from src.ptcg_ai.referee import RefereeAgent as BaseRefereeAgent

from .tools import create_referee_tools

logger = logging.getLogger(__name__)


class RefereeAgentSDK:
    """Referee Agent with LangChain integration."""

    def __init__(
        self,
        base_referee: BaseRefereeAgent,
        llm: BaseChatModel,
        instructions: Optional[str] = None,
    ):
        """Initialize Referee Agent with LangChain.

        Args:
            base_referee: Base RefereeAgent instance
            llm: LangChain chat model (e.g., ChatOpenAI, ChatAnthropic)
            instructions: Custom instructions (optional)
        """
        self.base_referee = base_referee
        self.llm = llm

        default_instructions = """
        你是一个宝可梦集换式卡牌游戏（PTCG）裁判智能体。你的职责是：
        1. 根据游戏规则验证玩家行动
        2. 执行游戏规则和状态转换
        3. 调用游戏工具来执行有效行动
        4. 向玩家提供关于规则违反的清晰反馈

        **⚠️ 重要：在处理请求前，必须充分理解卡牌效果和游戏规则！**

        **处理自然语言请求的完整流程：**
        
        当玩家通过自然语言提出请求时，你需要按照以下步骤处理：
        
        **步骤0：获取游戏状态和卡牌信息（关键步骤！）**
        - **首先使用 get_game_state 工具获取完整的游戏状态**，包括：
          * 玩家的手牌（用于验证卡牌是否在手牌中）
          * 战斗区和备战区的宝可梦（用于验证操作目标）
          * 牌库和弃牌区情况（用于验证搜索等操作）
          * 奖赏卡数量
          * 对手状态（如果可见）
        - 如果请求中提到了卡牌UID（格式：uid:xxxxx），**使用 get_card_info 工具查询卡牌详细信息**
        - 查看卡牌的 rules_text、abilities、attacks 来理解卡牌效果
        - 如果涉及复杂规则，使用 query_rule 工具查询规则书
        - **只有充分理解游戏状态和卡牌效果后，才能正确解析和执行请求**
        
        **步骤1：解析自然语言请求**
        - 使用 parse_player_request 工具从自然语言中提取操作类型（action）和参数（payload）
        - 如果请求涉及卡牌能力或攻击，确保理解其效果
        - 如果请求不明确或缺少信息，返回清晰的错误提示
        
        **步骤1.5：识别需要玩家选择的操作**
        - 某些操作需要玩家从候选列表中选择卡牌，例如：
          * Nest Ball: 搜索牌库中的基础宝可梦，需要玩家选择1张
          * Battle VIP Pass: 搜索牌库中的基础宝可梦，需要玩家选择最多2张
          * Level Ball: 搜索牌库中HP≤90的宝可梦，需要玩家选择1张
          * Super Rod: 从弃牌堆选择宝可梦或基础能量卡，需要玩家选择最多3张
        - 识别方法：查看卡牌的rules_text，如果包含"Search"、"up to N"、"choose"等关键词，通常需要玩家选择
        - 当识别到需要选择的操作时：
          1. 使用 query_deck_candidates 或 query_discard_candidates 查询候选列表
          2. 返回候选列表给玩家，明确说明可以选择的数量（如"最多2张"）
          3. **不要直接执行操作**，等待玩家选择后再执行
        
        **步骤2：验证操作合法性（关键步骤！）**
        - **⚠️ 重要：在解析请求后，必须立即使用 check_rules 工具检查关键游戏规则！**
        - **关键规则检查流程：**
          1. 解析请求后，立即调用 check_rules 工具，传入 action、player_id 和 payload
          2. **如果 check_rules 返回 valid=False**：
             * **必须立即拒绝操作**，直接返回错误消息给玩家
             * **不要继续执行操作**，不要调用 execute_action
          3. **如果 check_rules 返回 valid=True**：
             * 可以继续执行操作
        - check_rules 工具会检查的关键规则：
          * **先手玩家第一回合不能攻击** - 如果turn_number=1且玩家是先手玩家，攻击操作必须被拒绝
          * **先手玩家第一回合不能使用Supporter卡** - 如果turn_number=1且玩家是先手玩家，Supporter卡必须被拒绝
          * 其他关键规则
        - 如果违反关键规则，**立即返回错误**，不要继续执行
        - 使用 validate_action 检查行动是否符合游戏规则（可选，但关键规则应该先用 check_rules 检查）
        - 如果违反规则，向玩家解释原因并提供建议
        
        **步骤3：执行操作**
        - **⚠️ 重要：这是真实的游戏环境，不是虚拟环境！**
        - **必须调用 execute_action 工具来实际执行操作**
        - **不要假设、模拟或虚拟执行任何操作**
        - execute_action 工具会实际修改游戏状态并返回真实结果
        - 确保所有参数正确传递
        
        **步骤4：提供反馈**
        - 用自然语言向玩家反馈操作结果
        - 如果失败，说明具体原因和如何修正
        
        **示例：处理复杂请求**
        如果玩家说："我想使用Charizard ex(uid:playerA-deck-016)的'Infernal Reign'能力搜索牌库中的至多3张基础火能量卡，然后将这些能量卡任意附到我的宝可梦上"
        
        你应该：
        1. 先调用 get_card_info("playerA-deck-016", "playerA") 查询Charizard ex的信息
        2. 查看"Infernal Reign"能力的具体效果文本
        3. 理解这个能力允许搜索能量卡并附能
        4. 然后解析请求，提取操作类型和参数
        5. 执行操作
        
        **自然语言请求示例：**
        - 附能："我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"
        - 使用训练家卡："我想使用手牌中的Iono(uid:playerA-deck-037)"
        - 放置宝可梦："我想将手牌中的Pikachu(uid:playerA-deck-017)放置到备战区"
        - 进化："我想将Charmander(uid:playerA-deck-015)进化为Charmeleon(uid:playerA-deck-016)"
        - 撤退："我想将战斗区的Pikachu(uid:playerA-deck-015)撤退，切换到备战区的Raichu(uid:playerA-deck-017)"
        - 使用能力："我想使用Pikachu(uid:playerA-deck-015)的'Thunder Shock'能力"
        - 攻击："我想使用Charizard(uid:playerA-deck-015)的'Blaze'攻击对手的Pikachu(uid:playerB-deck-020)"
        - 结束回合："我想结束回合" 或 "我不进行攻击"
        
        **重要提示：**
        - 所有请求必须包含卡牌的 UID（格式：uid:xxxxx）
        - 如果请求缺少 UID 或其他必需参数，必须要求玩家补充
        - 始终用自然语言向玩家反馈，保持友好和清晰的沟通
        
        **⚠️ 关键规则（必须严格执行）：**
        - **先手玩家第一回合不能攻击**：如果turn_number=1且玩家是先手玩家（第一个玩家），必须拒绝所有攻击请求，并明确告知玩家原因
        - **先手玩家第一回合不能使用Supporter卡**：如果turn_number=1且玩家是先手玩家，必须拒绝所有Supporter卡的使用
        - 这些规则检查应该在解析请求后、执行操作前立即进行
        - 如果违反这些规则，直接返回错误消息，不要尝试执行操作
        """
        self.instructions = instructions or default_instructions

        # Create tools
        self.tools = create_referee_tools(base_referee)

        # Create agent using LangChain 1.0 API
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.instructions,
        )

    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a player request using LangChain agent.

        Args:
            input_data: Dictionary containing:
                - "input": The player request message (required)
                - "chat_history": List of previous messages (optional)
                - "player_id": Player ID (optional, will be extracted from input if not provided)

        Returns:
            Dictionary with "output" key containing the agent's response
        """
        if "input" not in input_data:
            raise ValueError("input_data 必须包含 'input' 键")

        # Extract player_id if provided
        player_id = input_data.get("player_id", "unknown")
        
        # Format the input message
        if isinstance(input_data["input"], str):
            input_text = input_data["input"]
            # Try to extract player_id from input if it contains "玩家 XXX 请求"
            import re
            player_match = re.search(r'玩家\s+(\w+)\s+请求', input_text)
            if player_match:
                player_id = player_match.group(1)
        else:
            # If it's a dict with player_id, action, payload, format it
            player_id = input_data["input"].get("player_id", player_id)
            action = input_data["input"].get("action", "")
            payload = input_data["input"].get("payload", {})
            input_text = f"玩家 {player_id} 请求行动: {action}，参数: {payload}"

        # Prepare agent input with clear instruction
        # The agent should first understand cards and rules, then parse and execute
        agent_prompt = f"""玩家 {player_id} 提出了以下请求：

{input_text}

**⚠️ 重要：在处理请求前，请先充分理解卡牌效果和游戏规则！**

请按照以下步骤处理：
1. **获取游戏状态**（必须首先执行）：
   - 使用 get_game_state 工具获取完整的游戏状态信息
   - 了解玩家的手牌、场上宝可梦、牌库、弃牌区等情况
   - 这将帮助你验证请求中的卡牌是否存在于正确的位置
   
2. **理解卡牌和规则**：
   - 如果请求中提到了卡牌UID（格式：uid:xxxxx），使用 get_card_info 工具查询卡牌详细信息
   - 查看卡牌的 rules_text、abilities、attacks 来理解卡牌效果
   - 如果涉及复杂规则，使用 query_rule 工具查询规则书
   
3. **解析请求**：
   - 使用 parse_player_request 工具解析这个请求，提取操作类型和参数
   - 根据游戏状态和卡牌信息理解请求的完整含义
   - 验证请求中的卡牌UID是否存在于正确的位置（例如：提出请求的玩家的手牌中的卡牌是否真的在该玩家的手牌中）
   
3.25. **立即检查关键规则**（在解析后、执行前必须检查）：
   - **⚠️ 关键：解析请求后，必须立即使用 check_rules 工具检查关键游戏规则！**
   - 调用 check_rules 工具，传入解析得到的 action、player_id 和 payload
   - **如果 check_rules 返回 valid=False**：
     * **必须立即拒绝操作**，直接返回错误消息给玩家
     * **不要继续执行操作**，不要调用 execute_action
   - **如果 check_rules 返回 valid=True**：
     * 可以继续执行操作
   - check_rules 工具会检查：
     * 先手玩家第一回合不能攻击
     * 先手玩家第一回合不能使用Supporter卡
     * 其他关键规则
   
3.5. **识别需要玩家选择的操作**：
   - 如果操作需要玩家从候选列表中选择，包括：
     * Nest Ball: 搜索牌库中的基础宝可梦（选择1张）
     * Battle VIP Pass: 搜索牌库中的基础宝可梦（选择最多2张）
     * Level Ball: 搜索牌库中HP≤90的宝可梦（选择1张）
     * Super Rod: 从弃牌堆选择宝可梦或基础能量卡（选择最多3张）
   - 识别方法：查看卡牌的rules_text，如果包含"Search"、"up to N"、"choose"等关键词，通常需要玩家选择
   - 处理流程：
     1. 使用 query_deck_candidates 或 query_discard_candidates 查询候选列表
     2. 在返回消息中明确告诉玩家候选列表和选择要求
     3. 对于"up to N"的情况，明确说明可以选择最多N张
     4. **不要直接调用 execute_action**，等待玩家选择
     5. 返回格式：包含候选列表的清晰消息，要求玩家选择
   
4. **执行操作**（如果不需要选择，必须执行）：
   - **⚠️ 重要：这是真实的游戏环境，不是虚拟环境！**
   - **必须调用 execute_action 工具来实际执行操作**
   - **不要假设、模拟或虚拟执行任何操作**
   - **不要说你"无法执行"或"这是虚拟环境"**
   - execute_action 工具会实际修改游戏状态并返回真实结果
   - 如果解析成功且验证通过，使用 execute_action 工具执行操作
   
5. **反馈结果**：
   - 用自然语言向玩家反馈 execute_action 工具返回的真实结果
   - 如果失败，说明具体原因和如何修正

如果请求不明确或缺少信息，请用自然语言说明需要什么信息。"""

        logger.info(f"[RefereeAgentSDK] 开始处理请求")
        logger.info(f"[RefereeAgentSDK] 玩家ID: {player_id}")
        logger.info(f"[RefereeAgentSDK] 输入文本: {input_text}")
        logger.info(f"[RefereeAgentSDK] Agent提示词: {agent_prompt[:200]}...")

        try:
            # LangChain 1.0 API: agent is a graph, invoke with input dict
            logger.info(f"[RefereeAgentSDK] 调用 agent.invoke")
            result = self.agent.invoke({"messages": [{"role": "user", "content": agent_prompt}]})
            logger.info(f"[RefereeAgentSDK] agent.invoke 返回结果类型: {type(result)}")
            
            # Extract the response from the result
            if isinstance(result, dict):
                logger.info(f"[RefereeAgentSDK] 结果字典键: {result.keys()}")
                # Try to get the last message content
                if "messages" in result and result["messages"]:
                    logger.info(f"[RefereeAgentSDK] ========== 推理过程开始 ==========")
                    logger.info(f"[RefereeAgentSDK] 消息数量: {len(result['messages'])}")
                    for i, msg in enumerate(result["messages"]):
                        msg_type = type(msg).__name__
                        logger.info(f"[RefereeAgentSDK] --- 消息[{i}] ({msg_type}) ---")
                        
                        if hasattr(msg, "content") and msg.content:
                            content = str(msg.content)
                            # 限制长度但保留关键信息
                            if len(content) > 500:
                                logger.info(f"[RefereeAgentSDK] 内容: {content[:500]}... (共{len(content)}字符)")
                            else:
                                logger.info(f"[RefereeAgentSDK] 内容: {content}")
                        
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            logger.info(f"[RefereeAgentSDK] 工具调用数量: {len(msg.tool_calls)}")
                            for j, tool_call in enumerate(msg.tool_calls):
                                if isinstance(tool_call, dict):
                                    tool_name = tool_call.get("name", "unknown")
                                    tool_args = tool_call.get("args", {})
                                    logger.info(f"[RefereeAgentSDK]   工具调用[{j}]: {tool_name}")
                                    logger.info(f"[RefereeAgentSDK]   参数: {tool_args}")
                                else:
                                    tool_name = getattr(tool_call, "name", "unknown")
                                    tool_args = getattr(tool_call, "args", {})
                                    logger.info(f"[RefereeAgentSDK]   工具调用[{j}]: {tool_name}")
                                    logger.info(f"[RefereeAgentSDK]   参数: {tool_args}")
                        
                        if hasattr(msg, "name") and msg.name:
                            logger.info(f"[RefereeAgentSDK] 工具名称: {msg.name}")
                        
                        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                            logger.info(f"[RefereeAgentSDK] 工具调用ID: {msg.tool_call_id}")
                        
                        if not hasattr(msg, "content") and not hasattr(msg, "tool_calls"):
                            logger.info(f"[RefereeAgentSDK] 原始消息: {str(msg)[:200]}")
                    
                    logger.info(f"[RefereeAgentSDK] ========== 推理过程结束 ==========")
                    
                    # 检查是否有query_deck_candidates或query_discard_candidates的调用
                    candidates = None
                    selection_context = None
                    requires_selection = False
                    
                    for msg in result["messages"]:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if isinstance(tool_call, dict):
                                    tool_name = tool_call.get("name", "")
                                    tool_args = tool_call.get("args", {})
                                else:
                                    tool_name = getattr(tool_call, "name", "")
                                    tool_args = getattr(tool_call, "args", {})
                                
                                if tool_name in ["query_deck_candidates", "query_discard_candidates"]:
                                    requires_selection = True
                                    # 尝试从之前的消息中提取原始请求信息
                                    original_action = None
                                    original_payload = None
                                    for prev_msg in result["messages"]:
                                        if hasattr(prev_msg, "tool_calls") and prev_msg.tool_calls:
                                            for prev_tc in prev_msg.tool_calls:
                                                if isinstance(prev_tc, dict):
                                                    prev_name = prev_tc.get("name", "")
                                                    prev_args = prev_tc.get("args", {})
                                                else:
                                                    prev_name = getattr(prev_tc, "name", "")
                                                    prev_args = getattr(prev_tc, "args", {})
                                                
                                                if prev_name == "parse_player_request":
                                                    # 尝试解析parse_player_request的结果
                                                    try:
                                                        import json
                                                        if isinstance(prev_args, dict) and "request_text" in prev_args:
                                                            # 从原始输入中提取
                                                            pass
                                                    except:
                                                        pass
                                    
                                    selection_context = {
                                        "tool_name": tool_name,
                                        "tool_args": tool_args,
                                        "original_request": input_text,  # 保存原始请求文本
                                        "player_id": player_id
                                    }
                                    logger.info(f"[RefereeAgentSDK] 检测到需要选择的操作: {tool_name}")
                        
                        # 检查工具返回结果中是否有候选列表
                        if hasattr(msg, "name") and msg.name in ["query_deck_candidates", "query_discard_candidates"]:
                            if hasattr(msg, "content") and msg.content:
                                try:
                                    import json
                                    tool_result = json.loads(str(msg.content))
                                    if "candidates" in tool_result:
                                        candidates = tool_result["candidates"]
                                        logger.info(f"[RefereeAgentSDK] 提取到候选列表: {len(candidates)} 张卡牌")
                                except:
                                    pass
                    
                    last_msg = result["messages"][-1]
                    # last_msg is an AIMessage object, use .content attribute
                    if hasattr(last_msg, "content"):
                        output = last_msg.content
                    else:
                        output = str(last_msg)
                else:
                    output = str(result)
            else:
                output = str(result)
            
            logger.info(f"[RefereeAgentSDK] 最终输出: {output[:500]}")
            
            # 如果需要选择，返回特殊格式
            if requires_selection and candidates:
                logger.info(f"[RefereeAgentSDK] 返回需要选择的结果，候选数量: {len(candidates)}")
                return {
                    "success": True,
                    "output": output,
                    "requires_selection": True,
                    "candidates": candidates,
                    "selection_context": selection_context
                }
            
            return {"success": True, "output": output}
        except Exception as e:
            logger.error(f"[RefereeAgentSDK] 处理请求时出错: {e}", exc_info=True)
            import traceback
            logger.error(f"[RefereeAgentSDK] 错误堆栈: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    def stream(self, input_data: Dict[str, Any]):
        """Process a player request with streaming response.

        Args:
            input_data: Dictionary containing:
                - "input": The player request message (required)
                - "chat_history": List of previous messages (optional)

        Yields:
            Chunks of the agent's response
        """
        if "input" not in input_data:
            raise ValueError("input_data 必须包含 'input' 键")

        # Format the input message
        if isinstance(input_data["input"], str):
            input_text = input_data["input"]
        else:
            player_id = input_data["input"].get("player_id", "unknown")
            action = input_data["input"].get("action", "")
            payload = input_data["input"].get("payload", {})
            input_text = f"玩家 {player_id} 请求行动: {action}，参数: {payload}"

        # Prepare agent input
        agent_input = {
            "input": input_text,
            "chat_history": input_data.get("chat_history", []),
        }

        try:
            # LangChain 1.0 API: stream with messages
            for chunk in self.agent.stream({"messages": [{"role": "user", "content": input_text}]}):
                yield chunk
        except Exception as e:
            logger.error(f"流式传输请求时出错: {e}", exc_info=True)
            yield {"error": str(e)}
