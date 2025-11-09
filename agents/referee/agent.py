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

        在执行行动前，始终检查规则。如果行动违反规则，
        请解释原因并建议替代方案。

        处理玩家请求时：
        1. 首先使用 validate_action 检查行动是否有效
        2. 如果有效，使用 execute_action 执行行动
        3. 如果需要检查规则，使用 query_rule 搜索知识库
        4. 提供关于结果的清晰反馈
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

        Returns:
            Dictionary with "output" key containing the agent's response
        """
        if "input" not in input_data:
            raise ValueError("input_data 必须包含 'input' 键")

        # Format the input message
        if isinstance(input_data["input"], str):
            input_text = input_data["input"]
        else:
            # If it's a dict with player_id, action, payload, format it
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
            # LangChain 1.0 API: agent is a graph, invoke with input dict
            result = self.agent.invoke({"messages": [{"role": "user", "content": input_text}]})
            # Extract the response from the result
            if isinstance(result, dict):
                # Try to get the last message content
                if "messages" in result and result["messages"]:
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
            return {"success": True, "output": output}
        except Exception as e:
            logger.error(f"处理请求时出错: {e}", exc_info=True)
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
