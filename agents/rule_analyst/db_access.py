"""Database access functions for card execution plans."""
from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime

from .analyzer import CardExecutionPlan

logger = logging.getLogger(__name__)


def save_plan_to_db(plan: CardExecutionPlan, dsn: Optional[str] = None) -> bool:
    """保存卡牌预案到数据库。
    
    Args:
        plan: CardExecutionPlan对象
        dsn: 数据库连接字符串（可选，如果为None则使用环境变量）
        
    Returns:
        True if successful, False otherwise
    """
    import psycopg
    from psycopg.types.json import Jsonb
    
    try:
        if dsn is None:
            import os
            dsn = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/ptcg"
        
        conn = psycopg.connect(dsn)
        
        try:
            with conn.cursor() as cur:
                # 检查是否已存在相同card_id、effect_name和version的记录
                # 对于有多个效果的卡牌，每个效果应该有独立的记录
                cur.execute(
                    """
                    SELECT id FROM card_execution_plans
                    WHERE card_id = %s AND version = %s AND effect_name = %s
                    """,
                    (plan.card_id, plan.version, plan.effect_name)
                )
                existing_row = cur.fetchone()
                existing = existing_row
                
                # 如果没有找到匹配的 effect_name，且 plan 有 effect_name，则插入新记录
                # 这样可以支持同一张卡牌的多个效果（能力/攻击）
                
                plan_dict = plan.to_dict()
                
                # 将 effect_type、effect_name、effect_subtype 信息编码到 analysis_notes 中
                # 格式：JSON字符串，包含这些信息
                import json
                import re
                effect_info = {
                    "effect_type": plan.effect_type,
                    "effect_name": plan.effect_name,
                    "effect_subtype": plan.effect_subtype
                }
                effect_info_str = json.dumps(effect_info, ensure_ascii=False)
                # 如果已有 analysis_notes，追加；否则新建
                if plan_dict.get("analysis_notes"):
                    plan_dict["analysis_notes"] = f"{plan_dict['analysis_notes']}\n[EFFECT_INFO]{effect_info_str}[/EFFECT_INFO]"
                else:
                    plan_dict["analysis_notes"] = f"[EFFECT_INFO]{effect_info_str}[/EFFECT_INFO]"
                
                if existing:
                    # 更新现有记录
                    cur.execute(
                        """
                        UPDATE card_execution_plans
                        SET card_name = %s,
                            set_code = %s,
                            number = %s,
                            requires_selection = %s,
                            selection_source = %s,
                            selection_criteria = %s,
                            max_selection_count = %s,
                            execution_steps = %s,
                            restrictions = %s,
                            validation_rules = %s,
                            status = %s,
                            effect_name = %s,
                            analysis_notes = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            plan_dict["card_name"],
                            plan_dict["set_code"],
                            plan_dict["number"],
                            plan_dict["requires_selection"],
                            plan_dict["selection_source"],
                            Jsonb(plan_dict["selection_criteria"]) if plan_dict["selection_criteria"] else None,
                            plan_dict["max_selection_count"],
                            Jsonb(plan_dict["execution_steps"]),
                            Jsonb(plan_dict["restrictions"]),
                            Jsonb(plan_dict["validation_rules"]),
                            plan_dict["status"],
                            plan_dict.get("effect_name"),
                            plan_dict["analysis_notes"],
                            existing[0]  # 使用 id 而不是 card_id + version
                        )
                    )
                    logger.info(f"[RuleAnalyst] 更新预案: {plan.card_id} ({plan.effect_name}) v{plan.version}")
                else:
                    # 插入新记录
                    cur.execute(
                        """
                        INSERT INTO card_execution_plans
                        (card_id, card_name, set_code, number,
                         requires_selection, selection_source, selection_criteria,
                         max_selection_count, execution_steps, restrictions,
                         validation_rules, status, version, effect_name, analysis_notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            plan_dict["card_id"],
                            plan_dict["card_name"],
                            plan_dict["set_code"],
                            plan_dict["number"],
                            plan_dict["requires_selection"],
                            plan_dict["selection_source"],
                            Jsonb(plan_dict["selection_criteria"]) if plan_dict["selection_criteria"] else None,
                            plan_dict["max_selection_count"],
                            Jsonb(plan_dict["execution_steps"]),
                            Jsonb(plan_dict["restrictions"]),
                            Jsonb(plan_dict["validation_rules"]),
                            plan_dict["status"],
                            plan_dict["version"],
                            plan_dict.get("effect_name"),
                            plan_dict["analysis_notes"]
                        )
                    )
                    logger.info(f"[RuleAnalyst] 保存新预案: {plan.card_id} ({plan.effect_name}) v{plan.version}")
                
                conn.commit()
                return True
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"[RuleAnalyst] 保存预案失败: {e}", exc_info=True)
        return False


def load_plan_from_db(card_id: str, effect_name: Optional[str] = None, version: Optional[int] = None, status: Optional[str] = "approved", dsn: Optional[str] = None) -> Optional[CardExecutionPlan]:
    """从数据库加载卡牌预案。
    
    Args:
        card_id: 卡牌ID（格式：set_code-number）
        effect_name: 效果名称（可选，用于匹配特定的能力/攻击）
        version: 版本号（可选，如果为None则加载最新版本）
        status: 状态过滤（默认只加载approved状态的预案）
        dsn: 数据库连接字符串（可选）
        
    Returns:
        CardExecutionPlan对象，如果未找到则返回None
    """
    import psycopg
    
    try:
        if dsn is None:
            import os
            dsn = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/ptcg"
        
        conn = psycopg.connect(dsn)
        
        try:
            with conn.cursor() as cur:
                # 构建查询条件
                conditions = ["card_id = %s"]
                params = [card_id]
                
                # 如果指定了 effect_name，直接添加到查询条件
                if effect_name:
                    conditions.append("effect_name = %s")
                    params.append(effect_name)
                
                if version is not None:
                    conditions.append("version = %s")
                    params.append(version)
                
                if status:
                    conditions.append("status = %s")
                    params.append(status)
                
                where_clause = " AND ".join(conditions)
                
                # 添加 effect_name 到 SELECT 列表
                if version is not None:
                    # 加载指定版本
                    query = f"""
                        SELECT card_id, card_name, set_code, number,
                               requires_selection, selection_source, selection_criteria,
                               max_selection_count, execution_steps, restrictions,
                               validation_rules, status, reviewed_by, reviewed_at,
                               version, effect_name, analysis_notes
                        FROM card_execution_plans
                        WHERE {where_clause}
                        """
                else:
                    # 加载最新版本（按版本号降序）
                        query = f"""
                            SELECT card_id, card_name, set_code, number,
                                   requires_selection, selection_source, selection_criteria,
                                   max_selection_count, execution_steps, restrictions,
                                   validation_rules, status, reviewed_by, reviewed_at,
                               version, effect_name, analysis_notes
                            FROM card_execution_plans
                            WHERE {where_clause}
                            ORDER BY version DESC
                            LIMIT 1
                            """
                
                cur.execute(query, tuple(params))
                row = cur.fetchone()
                
                if row:
                    plan_dict = {
                        "card_id": row[0],
                        "card_name": row[1],
                        "set_code": row[2],
                        "number": row[3],
                        "requires_selection": row[4],
                        "selection_source": row[5],
                        "selection_criteria": row[6],
                        "max_selection_count": row[7],
                        "execution_steps": row[8],
                        "restrictions": row[9],
                        "validation_rules": row[10],
                        "status": row[11],
                        "reviewed_by": row[12],
                        "reviewed_at": row[13],
                        "version": row[14],
                        "effect_name": row[15] if len(row) > 15 else None,
                        "analysis_notes": row[16] if len(row) > 16 else None
                    }
                    # 从 analysis_notes 中解析 effect_type、effect_subtype（如果 effect_name 字段为空，则也从 analysis_notes 中提取）
                    import json
                    import re
                    analysis_notes = plan_dict.get("analysis_notes", "")
                    if analysis_notes:
                        effect_info_match = re.search(r'\[EFFECT_INFO\](.*?)\[/EFFECT_INFO\]', analysis_notes, re.DOTALL)
                        if effect_info_match:
                            try:
                                effect_info = json.loads(effect_info_match.group(1))
                                if not plan_dict.get("effect_name"):
                                    plan_dict["effect_name"] = effect_info.get("effect_name")
                                plan_dict["effect_type"] = effect_info.get("effect_type")
                                plan_dict["effect_subtype"] = effect_info.get("effect_subtype")
                            except:
                                pass
                    
                    plan = CardExecutionPlan.from_dict(plan_dict)
                    return plan
                else:
                    logger.info(f"[RuleAnalyst] 未找到预案: card_id={card_id}, effect_name={effect_name}, version={version}, status={status}")
                    return None
                    
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"[RuleAnalyst] 加载预案失败: {e}", exc_info=True)
        return None

