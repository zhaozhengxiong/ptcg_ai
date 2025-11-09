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
        You are a PTCG (Pokémon Trading Card Game) player agent using the {strategy} strategy.
        Your goal is to win the game by:
        1. Making optimal decisions based on the current game state
        2. Managing your resources (cards, energy, prizes) effectively
        3. Anticipating opponent moves
        4. Adapting your strategy based on game state

        Analyze the game state carefully before making decisions. Consider:
        - Your hand and deck composition
        - Available Pokémon and their abilities
        - Energy requirements for attacks
        - Prize card count
        - Opponent's board state (if visible)

        Make decisions that maximize your chances of winning.

        When making a decision:
        1. Use analyze_game_state to understand the current situation
        2. Use remember to store important observations for future reference
        3. Use decide_action to choose your next move
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
        input_text = f"Current game state observation: {json.dumps(observation, default=str)}"

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
            logger.error(f"Error making decision: {e}", exc_info=True)
            # Fallback to base agent
            return self.base_agent.decide(observation)

    def stream(self, observation: Dict[str, Any]):
        """Make a decision with streaming response.

        Args:
            observation: Current game state observation

        Yields:
            Chunks of the agent's response
        """
        input_text = f"Current game state observation: {json.dumps(observation, default=str)}"

        try:
            # LangChain 1.0 API: stream with messages
            for chunk in self.agent.stream({"messages": [{"role": "user", "content": input_text}]}):
                yield chunk
        except Exception as e:
            logger.error(f"Error streaming decision: {e}", exc_info=True)
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
