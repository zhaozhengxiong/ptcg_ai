"""Rule Analyst Agent SDK for analyzing card effects."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel

from src.ptcg_ai.models import CardDefinition
from .analyzer import CardExecutionPlan, analyze_card_effect
from .db_access import save_plan_to_db, load_plan_from_db

logger = logging.getLogger(__name__)


class RuleAnalystAgentSDK:
    """Rule Analyst Agent with LangChain integration for analyzing card effects."""

    def __init__(
        self,
        llm: BaseChatModel,
    ):
        """Initialize Rule Analyst Agent.
        
        Args:
            llm: LangChain chat model (e.g., ChatOpenAI, ChatAnthropic)
        """
        self.llm = llm

    def analyze_card(self, card_definition: CardDefinition) -> CardExecutionPlan:
        """分析单张卡牌的效果并生成执行预案。
        
        Args:
            card_definition: 卡牌定义对象
            
        Returns:
            CardExecutionPlan对象
        """
        logger.info(f"[RuleAnalyst] 开始分析卡牌: {card_definition.name}")
        
        # 使用analyzer模块分析卡牌
        plan = analyze_card_effect(card_definition)
        
        logger.info(f"[RuleAnalyst] 分析完成: requires_selection={plan.requires_selection}")
        
        return plan

    def save_plan(self, plan: CardExecutionPlan, dsn: Optional[str] = None) -> bool:
        """保存预案到数据库。
        
        Args:
            plan: CardExecutionPlan对象
            dsn: 数据库连接字符串（可选）
            
        Returns:
            True if successful, False otherwise
        """
        return save_plan_to_db(plan, dsn)

    def load_plan(self, card_id: str, version: Optional[int] = None, status: Optional[str] = "approved", dsn: Optional[str] = None) -> Optional[CardExecutionPlan]:
        """从数据库加载预案。
        
        Args:
            card_id: 卡牌ID（格式：set_code-number）
            version: 版本号（可选）
            status: 状态过滤（默认只加载approved）
            dsn: 数据库连接字符串（可选）
            
        Returns:
            CardExecutionPlan对象，如果未找到则返回None
        """
        return load_plan_from_db(card_id, version, status, dsn)

    def analyze_and_save(self, card_definition: CardDefinition, dsn: Optional[str] = None) -> CardExecutionPlan:
        """分析卡牌并保存到数据库。
        
        Args:
            card_definition: 卡牌定义对象
            dsn: 数据库连接字符串（可选）
            
        Returns:
            CardExecutionPlan对象
        """
        plan = self.analyze_card(card_definition)
        if self.save_plan(plan, dsn):
            logger.info(f"[RuleAnalyst] 预案已保存: {plan.card_id}")
        else:
            logger.warning(f"[RuleAnalyst] 预案保存失败: {plan.card_id}")
        return plan

