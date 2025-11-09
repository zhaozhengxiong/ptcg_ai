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

logger = logging.getLogger(__name__)


class PlayerAgentSDK:
    """Player Agent with LangChain integration."""

    def __init__(
        self,
        base_agent: BasePlayerAgent,
        llm: BaseChatModel,
        strategy: str = "default",
        instructions: Optional[str] = None,
    ):
        """Initialize Player Agent with LangChain.

        Args:
            base_agent: Base PlayerAgent instance
            llm: LangChain chat model (e.g., ChatOpenAI, ChatAnthropic)
            strategy: Strategy name for the player
            instructions: Custom instructions (optional)
        """
        self.base_agent = base_agent
        self.llm = llm
        self.strategy = strategy

        default_instructions = f"""
        你是一个使用 {strategy} 策略的宝可梦集换式卡牌游戏（PTCG）玩家智能体。
        你的目标是通过以下方式赢得游戏：
        1. 根据当前游戏状态做出最优决策
        2. 有效管理你的资源（卡牌、能量、奖赏卡）
        3. 预测对手的行动
        4. 根据游戏状态调整你的策略

        在做出决策前，请仔细分析游戏状态。考虑以下因素：
        - 你的手牌和牌库组成
        - 可用的宝可梦及其能力
        - 攻击所需的能量要求
        - 奖赏卡数量
        - 对手的场上状态（如果可见）

        做出能够最大化获胜机会的决策。

        在做出决策时：
        1. 使用 analyze_game_state 来理解当前情况
        2. 使用 remember 来存储重要的观察结果以供将来参考
        3. 使用 decide_action 来选择你的下一步行动
        """
        self.instructions = instructions or default_instructions

        # Create tools
        self.tools = create_player_tools(base_agent)

        # Create agent using LangChain 1.0 API
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.instructions,
        )

    def invoke(self, observation: Dict[str, Any]) -> Optional[OperationRequest]:
        """Make a decision based on game observation using LangChain agent.

        Args:
            observation: Current game state observation

        Returns:
            OperationRequest if action is decided, None otherwise
        """
        # Format the observation as input
        input_text = f"当前游戏状态观察: {json.dumps(observation, default=str)}"

        try:
            # LangChain 1.0 API: agent is a graph, invoke with messages
            result = self.agent.invoke({"messages": [{"role": "user", "content": input_text}]})
            # Extract the response from the result
            if isinstance(result, dict):
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

            # Try to parse action from output
            # The agent should use decide_action tool, but we also try to parse from text
            parsed_action = self._parse_action_from_response(output, observation)
            return parsed_action
        except Exception as e:
            logger.error(f"做出决策时出错: {e}", exc_info=True)
            # Fallback to base agent
            return self.base_agent.decide(observation)

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

        # Fallback: simple keyword matching
        response_lower = response_text.lower()
        if "draw" in response_lower:
            return OperationRequest(
                actor_id=self.base_agent.player_id,
                action="draw",
                payload={"count": 1},
            )

        # Fallback to base agent
        return self.base_agent.decide(observation)
