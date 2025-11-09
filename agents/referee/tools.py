"""LangChain tools for Referee Agent."""
from __future__ import annotations

import json
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.ptcg_ai.referee import OperationRequest, RefereeAgent


class ValidateActionInput(BaseModel):
    """Input schema for validate_action tool."""

    action: str = Field(description="行动类型（draw, discard, attack 等）")
    player_id: str = Field(description="执行行动的玩家ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动特定的参数")


class QueryRuleInput(BaseModel):
    """Input schema for query_rule tool."""

    query: str = Field(description="在规则中搜索的查询字符串")
    limit: int = Field(default=5, description="最大结果数量")


class ExecuteActionInput(BaseModel):
    """Input schema for execute_action tool."""

    action: str = Field(description="要执行的行动")
    player_id: str = Field(description="玩家ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="行动参数")


def create_referee_tools(base_referee: RefereeAgent) -> list[StructuredTool]:
    """Create LangChain tools for the referee agent.

    Args:
        base_referee: Base RefereeAgent instance

    Returns:
        List of StructuredTool instances
    """
    def validate_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """根据游戏规则验证玩家行动。"""
        request = OperationRequest(
            actor_id=player_id,
            action=action,
            payload=payload,
        )
        result = base_referee.handle_request(request)
        return json.dumps({"valid": result.success, "message": result.message})

    def query_rule(query: str, limit: int = 5) -> str:
        """在规则知识库中查询相关规则。"""
        matches = base_referee.knowledge_base.find(query, limit=limit)
        results = [{"section": m.section, "text": m.text} for m in matches]
        return json.dumps(results)

    def execute_action(action: str, player_id: str, payload: Dict[str, Any]) -> str:
        """使用游戏工具执行已验证的行动。"""
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
        description="根据游戏规则验证玩家行动。返回包含成功状态和消息的验证结果。",
        args_schema=ValidateActionInput,
    )

    query_rule_tool = StructuredTool.from_function(
        func=query_rule,
        name="query_rule",
        description="在规则知识库中查询相关规则。返回匹配的规则章节和文本。",
        args_schema=QueryRuleInput,
    )

    execute_action_tool = StructuredTool.from_function(
        func=execute_action,
        name="execute_action",
        description="使用游戏工具执行已验证的行动。返回包含成功状态和数据的执行结果。",
        args_schema=ExecuteActionInput,
    )

    return [validate_action_tool, query_rule_tool, execute_action_tool]

