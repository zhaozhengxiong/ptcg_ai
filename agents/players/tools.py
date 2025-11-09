"""LangChain tools for Player Agent."""
from __future__ import annotations

import json
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent


class AnalyzeGameStateInput(BaseModel):
    """Input schema for analyze_game_state tool."""

    observation: Dict[str, Any] = Field(description="当前游戏状态观察")


class DecideActionInput(BaseModel):
    """Input schema for decide_action tool."""

    action: str = Field(description="行动类型（draw, play_card, attack 等）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动特定的参数")


class RememberInput(BaseModel):
    """Input schema for remember tool."""

    content: str = Field(description="要存储的记忆内容")


def create_player_tools(base_agent: BasePlayerAgent) -> list[StructuredTool]:
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

    def decide_action(action: str, payload: Dict[str, Any]) -> str:
        """决定下一步要采取的行动。"""
        return json.dumps({
            "action": action,
            "payload": payload,
        })

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
        description="决定下一步要采取的行动。返回行动类型和参数。",
        args_schema=DecideActionInput,
    )

    remember_tool = StructuredTool.from_function(
        func=remember,
        name="remember",
        description="存储关于游戏的记忆以供将来参考。使用此工具来记住重要的游戏事件或策略。",
        args_schema=RememberInput,
    )

    return [analyze_game_state_tool, decide_action_tool, remember_tool]

