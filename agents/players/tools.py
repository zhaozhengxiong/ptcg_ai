"""LangChain tools for Player Agent."""
from __future__ import annotations

import json
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent


class AnalyzeGameStateInput(BaseModel):
    """Input schema for analyze_game_state tool."""

    observation: Dict[str, Any] = Field(description="Current game state observation")


class DecideActionInput(BaseModel):
    """Input schema for decide_action tool."""

    action: str = Field(description="Action type (draw, play_card, attack, etc.)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class RememberInput(BaseModel):
    """Input schema for remember tool."""

    content: str = Field(description="Memory content to store")


def create_player_tools(base_agent: BasePlayerAgent) -> list[StructuredTool]:
    """Create LangChain tools for the player agent.

    Args:
        base_agent: Base PlayerAgent instance

    Returns:
        List of StructuredTool instances
    """
    def analyze_game_state(observation: Dict[str, Any]) -> str:
        """Analyze the current game state to inform decision making."""
        analysis = {
            "hand_size": observation.get("hand_size", 0),
            "prizes": observation.get("prizes", 6),
            "memory_count": len(base_agent.memory.thoughts),
            "observation": observation,
        }
        return json.dumps(analysis)

    def decide_action(action: str, payload: Dict[str, Any]) -> str:
        """Decide on the next action to take."""
        return json.dumps({
            "action": action,
            "payload": payload,
        })

    def remember(content: str) -> str:
        """Store a memory about the game for future reference."""
        base_agent.memory.remember(content)
        return json.dumps({"success": True, "message": "Memory stored"})

    analyze_game_state_tool = StructuredTool.from_function(
        func=analyze_game_state,
        name="analyze_game_state",
        description="Analyze the current game state to inform decision making. Returns analysis including hand size, prizes, and memory count.",
        args_schema=AnalyzeGameStateInput,
    )

    decide_action_tool = StructuredTool.from_function(
        func=decide_action,
        name="decide_action",
        description="Decide on the next action to take. Returns the action type and payload.",
        args_schema=DecideActionInput,
    )

    remember_tool = StructuredTool.from_function(
        func=remember,
        name="remember",
        description="Store a memory about the game for future reference. Use this to remember important game events or strategies.",
        args_schema=RememberInput,
    )

    return [analyze_game_state_tool, decide_action_tool, remember_tool]

