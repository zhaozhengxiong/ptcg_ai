#!/usr/bin/env python3
"""使用 rule_analyst 分析卡组文件中的卡牌，输出分析结果供确认后保存到数据库。"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg
except ImportError:
    print("错误: 需要安装 psycopg")
    print("请运行: pip install 'psycopg[binary]'")
    sys.exit(1)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.rule_analyst import RuleAnalystAgentSDK, analyze_card_effect, analyze_all_card_effects, save_plan_to_db
from agents.rule_analyst.pattern_matcher import RulePatternMatcher
from agents.rule_analyst.rulebook_query import create_rulebook_query
from src.ptcg_ai.card_loader import _map_card_fields
from src.ptcg_ai.database import build_postgres_dsn

# 尝试导入 LLM，如果失败则使用基础功能
try:
    from langchain_openai import ChatOpenAI
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


def parse_deck_file(deck_file: Path) -> List[Tuple[int, str, str, str]]:
    """解析卡组文件，返回 (count, card_name, set_code, number) 列表。"""
    card_requirements = []
    
    lines = deck_file.read_text(encoding="utf-8").splitlines()
    section = "Unknown"
    
    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line and not line[0].isdigit():
            section = line.split(":", 1)[0].strip() or "Unknown"
            continue
        if not line[0].isdigit():
            continue
        
        parts = line.split()
        if len(parts) < 4:
            print(f"警告: 跳过格式错误的行 {line_num}: '{line}'")
            continue
        
        try:
            count = int(parts[0])
        except ValueError:
            print(f"警告: 跳过无效计数的行 {line_num}: '{line}'")
            continue
        
        set_code = parts[-2]
        number = parts[-1]
        card_name = " ".join(parts[1:-2]) if len(parts) > 3 else "Unknown"
        
        card_requirements.append((count, card_name, set_code, number))
    
    return card_requirements


def load_card_from_db(set_code: str, number: str, dsn: str):
    """从数据库加载卡牌定义。"""
    try:
        conn = psycopg.connect(dsn)
    except Exception as e:
        raise RuntimeError(f"数据库连接失败: {e}")
    
    try:
        with conn.cursor() as cur:
            # 尝试直接查询
            cur.execute(
                """
                SELECT name, supertype, subtypes, hp, rules, set_ptcgo_code, number,
                       abilities, attacks
                FROM ptcg_cards
                WHERE set_ptcgo_code = %s AND number = %s
                LIMIT 1
                """,
                (set_code, number),
            )
            row = cur.fetchone()
            
            # 如果直接查询失败，尝试通过 ptcg_sets 表连接查询
            if row is None:
                cur.execute(
                    """
                    SELECT c.name, c.supertype, c.subtypes, c.hp, c.rules,
                           COALESCE(c.set_ptcgo_code, s.ptcgo_code) as set_ptcgo_code,
                           c.number, c.abilities, c.attacks
                    FROM ptcg_cards c
                    LEFT JOIN ptcg_sets s ON c.set_id = s.id
                    WHERE s.ptcgo_code = %s AND c.number = %s
                    LIMIT 1
                    """,
                    (set_code, number),
                )
                row = cur.fetchone()
            
            if row is None:
                return None
            
            (
                db_name,
                db_supertype,
                db_subtypes,
                db_hp,
                db_rules,
                db_set_code,
                db_number,
                db_abilities,
                db_attacks,
            ) = row
            
            return _map_card_fields(
                db_name,
                db_supertype,
                db_subtypes,
                db_hp,
                db_rules,
                db_set_code,
                db_number,
                db_abilities,
                db_attacks,
            )
    finally:
        conn.close()


def analyze_pattern_coverage(rules_text: str) -> Dict[str, Any]:
    """使用 pattern_matcher 分析规则文本的模式覆盖情况。
    
    Returns:
        包含模式匹配统计信息的字典
    """
    if not rules_text:
        return {"patterns_found": [], "coverage": {}}
    
    coverage = {
        "conditions": [],
        "actions": [],
        "damage_calc": None,
        "multi_player": False,
        "optional_actions": [],
        "target_location": None,
    }
    
    # 解析条件
    conditions = RulePatternMatcher.parse_condition_clauses(rules_text)
    coverage["conditions"] = conditions
    
    # 解析动作序列
    actions = RulePatternMatcher.parse_action_sequence(rules_text)
    coverage["actions"] = actions
    
    # 解析伤害计算（如果是攻击）
    damage_calc = RulePatternMatcher.parse_damage_calculation(rules_text)
    coverage["damage_calc"] = damage_calc
    
    # 检查多玩家
    coverage["multi_player"] = RulePatternMatcher.is_multi_player(rules_text)
    
    # 解析可选动作
    optional_actions = RulePatternMatcher.parse_optional_actions(rules_text)
    coverage["optional_actions"] = optional_actions
    
    # 解析目标位置
    target_location = RulePatternMatcher.parse_target_location(rules_text)
    coverage["target_location"] = target_location
    
    # 解析能量附着（如果有）
    attach_action = RulePatternMatcher.parse_attach_action(rules_text)
    if attach_action:
        coverage["attach_action"] = attach_action
    
    # 统计发现的模式类型
    patterns_found = []
    for action in actions:
        action_type = action.get("type")
        if action_type:
            patterns_found.append(action_type)
    
    if damage_calc:
        patterns_found.append(f"damage_calc_{damage_calc.get('type')}")
    
    if coverage["multi_player"]:
        patterns_found.append("multi_player")
    
    if target_location:
        patterns_found.append(f"target_{target_location}")
    
    return {
        "patterns_found": list(set(patterns_found)),
        "coverage": coverage
    }


def format_plan_summary(plan, pattern_analysis: Optional[Dict[str, Any]] = None) -> str:
    """格式化预案摘要为可读字符串。
    
    Args:
        plan: CardExecutionPlan 对象
        pattern_analysis: 可选的模式分析结果
    """
    lines = []
    lines.append(f"  ┌─ 卡牌: {plan.card_name} ({plan.card_id})")
    lines.append(f"  ├─ 效果类型: {plan.effect_type or 'N/A'}")
    if plan.effect_subtype:
        lines.append(f"  ├─ 子类型: {plan.effect_subtype}")
    if plan.effect_name:
        lines.append(f"  ├─ 效果名称: {plan.effect_name}")
    lines.append(f"  ├─ 需要选择: {'是' if plan.requires_selection else '否'}")
    if plan.requires_selection:
        lines.append(f"  │  ├─ 选择来源: {plan.selection_source or 'N/A'}")
        lines.append(f"  │  ├─ 最大选择数: {plan.max_selection_count or 'N/A'}")
        if plan.selection_criteria:
            lines.append(f"  │  └─ 选择条件: {json.dumps(plan.selection_criteria, ensure_ascii=False)}")
    lines.append(f"  ├─ 验证规则数: {len(plan.validation_rules)}")
    lines.append(f"  ├─ 执行步骤数: {len(plan.execution_steps)}")
    
    # 显示规则文档引用
    if plan.rulebook_references and len(plan.rulebook_references) > 0:
        lines.append(f"  ├─ 规则文档引用: {len(plan.rulebook_references)} 个")
        for i, ref in enumerate(plan.rulebook_references, 1):
            rule_id = ref.get("rule_id", "N/A")
            pattern_type = ref.get("pattern_type", "")
            summary = ref.get("summary", "")
            if summary and len(summary) > 100:
                summary = summary[:100] + "..."
            lines.append(f"  │  ├─ [{i}] {rule_id}" + (f" ({pattern_type})" if pattern_type else ""))
            if summary:
                lines.append(f"  │  │   └─ {summary}")
    
    lines.append(f"  └─ 状态: {plan.status}")
    
    # 显示模式匹配分析结果（如果提供）
    if pattern_analysis:
        patterns = pattern_analysis.get("patterns_found", [])
        if patterns:
            lines.append(f"  ┌─ 识别的模式: {', '.join(sorted(patterns))}")
        coverage = pattern_analysis.get("coverage", {})
        if coverage.get("conditions"):
            lines.append(f"  ├─ 条件数: {len(coverage['conditions'])}")
        if coverage.get("actions"):
            action_types = [a.get("type", "unknown") for a in coverage["actions"]]
            lines.append(f"  ├─ 动作类型: {', '.join(sorted(set(action_types)))}")
        if coverage.get("multi_player"):
            lines.append(f"  ├─ 多玩家效果: 是")
        if coverage.get("target_location"):
            lines.append(f"  ├─ 目标位置: {coverage['target_location']}")
        if coverage.get("damage_calc"):
            calc = coverage["damage_calc"]
            calc_type = calc.get("type", "N/A")
            lines.append(f"  ├─ 伤害计算: {calc_type}")
            if calc_type == "damage_bonus_per":
                lines.append(f"  │   └─ 每{calc.get('condition', 'N/A')}增加{calc.get('bonus', 0)}点")
            elif calc_type == "damage_to_self":
                lines.append(f"  │   └─ 自伤: {calc.get('damage', 0)}点")
            elif calc_type == "damage_to_multiple":
                lines.append(f"  │   └─ 对{calc.get('count', 0)}个目标各造成{calc.get('damage', 0)}点")
        if coverage.get("optional_actions"):
            lines.append(f"  ├─ 可选动作数: {len(coverage['optional_actions'])}")
        if coverage.get("attach_action"):
            attach = coverage["attach_action"]
            if attach.get("source"):
                lines.append(f"  ├─ 能量来源: {attach['source']}")
            if attach.get("allow_multiple_targets"):
                lines.append(f"  ├─ 允许多目标: 是")
    
    # 显示验证规则
    if plan.validation_rules:
        lines.append("  ┌─ 验证规则:")
        for i, rule in enumerate(plan.validation_rules, 1):
            lines.append(f"  │  {i}. {rule.get('description', 'N/A')} ({rule.get('type', 'N/A')})")
    
    # 显示执行步骤
    if plan.execution_steps:
        lines.append("  ┌─ 执行步骤:")
        for i, step in enumerate(plan.execution_steps, 1):
            step_type = step.get('step_type', 'N/A')
            description = step.get('description', 'N/A')
            action = step.get('action', 'N/A')
            lines.append(f"  │  {i}. [{step_type}] {description}")
            lines.append(f"  │     操作: {action}")
            
            # 显示新动作类型的参数
            params = step.get('params', {})
            if step_type == "heal":
                amount = params.get('amount', 'N/A')
                target = params.get('target', 'N/A')
                lines.append(f"  │     治疗量: {amount}, 目标: {target}")
            elif step_type == "move_damage_counters":
                count = params.get('count', 'N/A')
                source = params.get('source', 'N/A')
                target = params.get('target', 'N/A')
                lines.append(f"  │     数量: {count}, 来源: {source}, 目标: {target}")
            elif step_type == "move_energy":
                count = params.get('count', 'N/A')
                energy_type = params.get('energy_type', 'N/A')
                source = params.get('source', 'N/A')
                target = params.get('target', 'N/A')
                lines.append(f"  │     数量: {count}, 能量类型: {energy_type}, 来源: {source}, 目标: {target}")
            elif step_type == "devolve":
                target = params.get('target', 'N/A')
                method = params.get('method', 'N/A')
                lines.append(f"  │     目标: {target}, 方法: {method}")
            elif step_type == "damage":
                base_damage = params.get('base_damage', 0)
                damage_modifiers = params.get('damage_modifiers', [])
                damage_calc = params.get('damage_calculation')
                lines.append(f"  │     基础伤害: {base_damage}")
                if damage_modifiers:
                    lines.append(f"  │     伤害修正器: {len(damage_modifiers)} 个")
                    for mod in damage_modifiers:
                        mod_type = mod.get('type', 'N/A')
                        if mod_type == "damage_to_self":
                            lines.append(f"  │       - 自伤: {mod.get('amount', 0)}点")
                        elif mod_type == "damage_to_multiple":
                            lines.append(f"  │       - 对多个目标: {mod.get('damage', 0)} x {mod.get('count', 0)}")
                        elif mod_type == "bonus_per":
                            condition = mod.get('condition', 'N/A')
                            bonus = mod.get('bonus', 0)
                            lines.append(f"  │       - 每{condition}增加{bonus}点")
                        elif mod_type == "bonus":
                            lines.append(f"  │       - 增加{mod.get('bonus', 0)}点")
                        elif mod_type == "attack_does_nothing":
                            lines.append(f"  │       - 攻击无效")
                        elif mod_type == "prize_based":
                            lines.append(f"  │       - 基于奖赏卡: 每张{mod.get('bonus_per_prize', 0)}点")
                if damage_calc:
                    calc_type = damage_calc.get('type', 'N/A')
                    lines.append(f"  │     伤害计算类型: {calc_type}")
                    if calc_type == "damage_bonus_per":
                        lines.append(f"  │       └─ 每{damage_calc.get('condition', 'N/A')}增加{damage_calc.get('bonus', 0)}点")
                    elif calc_type == "damage_bonus":
                        lines.append(f"  │       └─ 增加{damage_calc.get('bonus', 0)}点")
                    elif calc_type == "damage_to_self":
                        lines.append(f"  │       └─ 自伤: {damage_calc.get('damage', 0)}点")
                    elif calc_type == "damage_to_multiple":
                        lines.append(f"  │       └─ 对{damage_calc.get('count', 0)}个目标各造成{damage_calc.get('damage', 0)}点")
            
            # 显示 before_damage 标记
            if step.get('before_damage'):
                lines.append(f"  │     ⚠️ 在造成伤害之前执行")
            
            if step.get('optional'):
                lines.append(f"  │     (可选步骤)")
            if step.get('depends_on'):
                lines.append(f"  │     依赖步骤: {step.get('depends_on')}")
    
    return "\n".join(lines)


def main():
    """主函数。"""
    # 解析命令行参数
    if len(sys.argv) < 2:
        print("用法: python analyze_deck_with_rule_analyst.py <deck_file> [dsn]")
        print("示例: python analyze_deck_with_rule_analyst.py doc/deck/deck1.txt")
        sys.exit(1)
    
    deck_file = Path(sys.argv[1])
    if not deck_file.exists():
        print(f"错误: 卡组文件不存在: {deck_file}")
        sys.exit(1)
    
    dsn = sys.argv[2] if len(sys.argv) > 2 else build_postgres_dsn()
    
    print("=" * 80)
    print(f"分析卡组文件: {deck_file}")
    print(f"数据库连接: {dsn}")
    print("=" * 80)
    print()
    
    # 解析卡组文件
    print("正在解析卡组文件...")
    card_requirements = parse_deck_file(deck_file)
    print(f"✓ 找到 {len(card_requirements)} 种不同的卡牌")
    print()
    
    # 去重：每种卡牌只分析一次
    unique_cards = {}
    for count, card_name, set_code, number in card_requirements:
        key = (set_code, number)
        if key not in unique_cards:
            unique_cards[key] = (card_name, set_code, number)
    
    print(f"去重后需要分析 {len(unique_cards)} 种不同的卡牌")
    print()
    
    # 初始化 rule_analyst
    print("正在初始化 Rule Analyst...")
    analyst = None
    if LLM_AVAILABLE:
        try:
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
            analyst = RuleAnalystAgentSDK(llm)
            print("✓ Rule Analyst 初始化完成（使用 LLM）")
        except Exception as e:
            print(f"警告: LLM 初始化失败，将使用基础分析功能: {e}")
            analyst = None
    else:
        print("警告: langchain_openai 未安装，将使用基础分析功能（不需要 LLM）")
        print("✓ Rule Analyst 初始化完成（使用基础分析功能）")
    
    print()
    
    # 创建规则文档查询器
    print("正在初始化规则文档查询器...")
    rulebook_query = create_rulebook_query()
    print("✓ 规则文档查询器初始化完成")
    print()
    
    # 分析每张卡牌
    print("=" * 80)
    print("开始分析卡牌...")
    print("=" * 80)
    print()
    
    plans: Dict[str, any] = {}  # card_id -> plan
    pattern_analyses: Dict[str, Dict[str, Any]] = {}  # plan_key -> pattern_analysis
    failed_cards: List[str] = []
    pattern_stats = {
        "total_patterns": 0,
        "pattern_types": {},
        "new_patterns_found": set(),  # 新发现的模式类型
    }
    
    for idx, (card_name, set_code, number) in enumerate(unique_cards.values(), 1):
        card_id = f"{set_code}-{number}"
        print(f"[{idx}/{len(unique_cards)}] 分析: {card_name} ({card_id})")
        
        # 从数据库加载卡牌定义
        try:
            card_def = load_card_from_db(set_code, number, dsn)
            if card_def is None:
                print(f"  ✗ 错误: 数据库中未找到卡牌 {card_id}")
                failed_cards.append(card_id)
                print()
                continue
        except Exception as e:
            print(f"  ✗ 错误: 加载卡牌失败: {e}")
            failed_cards.append(card_id)
            print()
            continue
        
        # 分析卡牌（获取所有效果的预案）
        try:
            # 使用 analyze_all_card_effects 获取所有效果的预案，传入规则文档查询器
            card_plans = analyze_all_card_effects(card_def, rulebook_query=rulebook_query)
            
            # 为每个效果创建独立的预案条目
            for plan in card_plans:
                # 使用 card_id + effect_type + effect_name 作为唯一标识
                plan_key = f"{card_id}-{plan.effect_type or 'unknown'}-{plan.effect_name or 'unknown'}"
                plans[plan_key] = plan
                
                # 使用 pattern_matcher 分析规则文本
                rules_text = ""
                if plan.effect_type == "attack" and card_def.attacks:
                    for attack in card_def.attacks:
                        if attack.get("name") == plan.effect_name:
                            rules_text = attack.get("text", "")
                            break
                elif plan.effect_type == "ability" and card_def.abilities:
                    for ability in card_def.abilities:
                        if ability.get("name") == plan.effect_name:
                            rules_text = ability.get("text", "")
                            break
                elif plan.effect_type == "trainer":
                    rules_text = card_def.rules_text or ""
                
                if rules_text:
                    pattern_analysis = analyze_pattern_coverage(rules_text)
                    pattern_analyses[plan_key] = pattern_analysis
                    
                    # 统计模式
                    for pattern_type in pattern_analysis.get("patterns_found", []):
                        pattern_stats["pattern_types"][pattern_type] = pattern_stats["pattern_types"].get(pattern_type, 0) + 1
                        pattern_stats["total_patterns"] += 1
                        
                        # 检查是否是新模式
                        new_patterns = ["heal", "move_damage_counters", "move_energy", "devolve", 
                                       "damage_to_self", "damage_to_multiple", "attack_does_nothing",
                                       "before_damage"]
                        if any(np in pattern_type for np in new_patterns):
                            pattern_stats["new_patterns_found"].add(pattern_type)
            
            print(f"  ✓ 分析完成（生成了 {len(card_plans)} 个效果的预案）")
        except Exception as e:
            print(f"  ✗ 错误: 分析失败: {e}")
            failed_cards.append(card_id)
            import traceback
            traceback.print_exc()
        
        print()
    
    # 显示分析结果摘要
    print("=" * 80)
    print("分析结果摘要")
    print("=" * 80)
    print()
    
    if failed_cards:
        print(f"✗ 失败的卡牌 ({len(failed_cards)} 张):")
        for card_id in failed_cards:
            print(f"  - {card_id}")
        print()
    
    print(f"✓ 成功分析的效果 ({len(plans)} 个):")
    for plan_key, plan in plans.items():
        effect_desc = f"{plan.effect_type or 'unknown'}"
        if plan.effect_name:
            effect_desc += f" '{plan.effect_name}'"
        print(f"  - {plan.card_name} ({plan.card_id}) - {effect_desc}")
    print()
    
    # 显示模式匹配统计
    if pattern_stats["total_patterns"] > 0:
        print("=" * 80)
        print("模式匹配统计")
        print("=" * 80)
        print()
        print(f"总识别模式数: {pattern_stats['total_patterns']}")
        print(f"模式类型分布:")
        for pattern_type, count in sorted(pattern_stats["pattern_types"].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {pattern_type}: {count} 次")
        print()
        
        if pattern_stats["new_patterns_found"]:
            print(f"✨ 新发现的模式类型 ({len(pattern_stats['new_patterns_found'])} 种):")
            for new_pattern in sorted(pattern_stats["new_patterns_found"]):
                print(f"  - {new_pattern}")
    print()
    
    # 显示详细分析结果
    print("=" * 80)
    print("详细分析结果")
    print("=" * 80)
    print()
    
    for plan_key, plan in plans.items():
        print(f"效果: {plan.effect_type or 'unknown'}" + (f" '{plan.effect_name}'" if plan.effect_name else ""))
        pattern_analysis = pattern_analyses.get(plan_key)
        print(format_plan_summary(plan, pattern_analysis))
        print()
    
    # 等待用户确认
    print("=" * 80)
    print("确认保存")
    print("=" * 80)
    print()
    print(f"准备保存 {len(plans)} 个效果的分析结果到数据库。")
    print()
    
    while True:
        response = input("是否保存到数据库? (y/n): ").strip().lower()
        if response in ['y', 'yes', '是']:
            break
        elif response in ['n', 'no', '否']:
            print("已取消保存。")
            return
        else:
            print("请输入 y 或 n")
    
    # 保存到数据库
    print()
    print("正在保存到数据库...")
    print()
    
    saved_count = 0
    failed_save = []
    
    for plan_key, plan in plans.items():
        try:
            if analyst:
                success = analyst.save_plan(plan, dsn=dsn)
            else:
                success = save_plan_to_db(plan, dsn=dsn)
            
            effect_desc = f"{plan.effect_type or 'unknown'}"
            if plan.effect_name:
                effect_desc += f" '{plan.effect_name}'"
            
            if success:
                print(f"  ✓ 已保存: {plan.card_name} ({plan.card_id}) - {effect_desc}")
                saved_count += 1
            else:
                print(f"  ✗ 保存失败: {plan.card_name} ({plan.card_id}) - {effect_desc}")
                failed_save.append(plan_key)
        except Exception as e:
            effect_desc = f"{plan.effect_type or 'unknown'}"
            if plan.effect_name:
                effect_desc += f" '{plan.effect_name}'"
            print(f"  ✗ 保存失败: {plan.card_name} ({plan.card_id}) - {effect_desc}: {e}")
            failed_save.append(plan_key)
    
    print()
    print("=" * 80)
    print("保存完成")
    print("=" * 80)
    print()
    print(f"✓ 成功保存: {saved_count} 个效果")
    if failed_save:
        print(f"✗ 保存失败: {len(failed_save)} 个")
        for plan_key in failed_save:
            print(f"  - {plan_key}")
    print()


if __name__ == "__main__":
    main()

