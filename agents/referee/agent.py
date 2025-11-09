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
        You are a PTCG (Pokémon Trading Card Game) referee agent. Your role is to:
        1. Validate player actions according to game rules
        2. Enforce game rules and state transitions
        3. Call game tools to execute valid actions
        4. Provide clear feedback to players about rule violations

        Always check rules before executing actions. If an action violates rules,
        explain why and suggest alternatives.

        When processing a player request:
        1. First use validate_action to check if the action is valid
        2. If valid, use execute_action to perform the action
        3. If you need to check rules, use query_rule to search the knowledge base
        4. Provide clear feedback about the result
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
            raise ValueError("input_data must contain 'input' key")

        # Format the input message
        if isinstance(input_data["input"], str):
            input_text = input_data["input"]
        else:
            # If it's a dict with player_id, action, payload, format it
            player_id = input_data["input"].get("player_id", "unknown")
            action = input_data["input"].get("action", "")
            payload = input_data["input"].get("payload", {})
            input_text = f"Player {player_id} requests action: {action} with payload: {payload}"

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
            logger.error(f"Error processing request: {e}", exc_info=True)
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
            raise ValueError("input_data must contain 'input' key")

        # Format the input message
        if isinstance(input_data["input"], str):
            input_text = input_data["input"]
        else:
            player_id = input_data["input"].get("player_id", "unknown")
            action = input_data["input"].get("action", "")
            payload = input_data["input"].get("payload", {})
            input_text = f"Player {player_id} requests action: {action} with payload: {payload}"

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
            logger.error(f"Error streaming request: {e}", exc_info=True)
            yield {"error": str(e)}
