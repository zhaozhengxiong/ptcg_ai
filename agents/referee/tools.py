"""LangChain tools for Referee Agent."""
from __future__ import annotations

import json
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.ptcg_ai.referee import OperationRequest, RefereeAgent


class ValidateActionInput(BaseModel):
    """Input schema for validate_action tool."""

    action: str = Field(description="Action type (draw, discard, attack, etc.)")
    player_id: str = Field(description="Player ID performing the action")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class QueryRuleInput(BaseModel):
    """Input schema for query_rule tool."""

    query: str = Field(description="Query string to search for in rules")
    limit: int = Field(default=5, description="Maximum number of results")


class ExecuteActionInput(BaseModel):
    """Input schema for execute_action tool."""

    action: str = Field(description="Action to execute")
    player_id: str = Field(description="Player ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


def create_referee_tools(base_referee: RefereeAgent) -> list[StructuredTool]:
    """Create LangChain tools for the referee agent.

    Args:
        base_referee: Base RefereeAgent instance

    Returns:
        List of StructuredTool instances
    """
    def validate_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """Validate a player action against game rules."""
        request = OperationRequest(
            actor_id=player_id,
            action=action,
            payload=payload,
        )
        result = base_referee.handle_request(request)
        return json.dumps({"valid": result.success, "message": result.message})

    def query_rule(query: str, limit: int = 5) -> str:
        """Query the rule knowledge base for relevant rules."""
        matches = base_referee.knowledge_base.find(query, limit=limit)
        results = [{"section": m.section, "text": m.text} for m in matches]
        return json.dumps(results)

    def execute_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """Execute a validated action using game tools."""
        request = OperationRequest(
            actor_id=player_id,
            action=action,
            payload=payload,
        )
        result = base_referee.handle_request(request)
        return json.dumps({"success": result.success, "data": result.data})

    validate_action_tool = StructuredTool.from_function(
        func=validate_action,
        name="validate_action",
        description="Validate a player action against game rules. Returns validation result with success status and message.",
        args_schema=ValidateActionInput,
    )

    query_rule_tool = StructuredTool.from_function(
        func=query_rule,
        name="query_rule",
        description="Query the rule knowledge base for relevant rules. Returns matching rule sections and text.",
        args_schema=QueryRuleInput,
    )

    execute_action_tool = StructuredTool.from_function(
        func=execute_action,
        name="execute_action",
        description="Execute a validated action using game tools. Returns execution result with success status and data.",
        args_schema=ExecuteActionInput,
    )

    return [validate_action_tool, query_rule_tool, execute_action_tool]

