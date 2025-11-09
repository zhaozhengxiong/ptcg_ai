"""Example script demonstrating LangChain Agents integration."""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Add project root to Python path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agents.referee import RefereeAgentSDK
from agents.players import PlayerAgentSDK
# 直接导入 rulebook_query 模块，避免触发 __init__.py 的导入
import importlib.util
from pathlib import Path
_rulebook_query_path = Path(__file__).parent.parent / "agents" / "rule_analyst" / "rulebook_query.py"
_rulebook_query_spec = importlib.util.spec_from_file_location("rulebook_query", _rulebook_query_path)
_rulebook_query_module = importlib.util.module_from_spec(_rulebook_query_spec)
import sys
sys.modules["rulebook_query"] = _rulebook_query_module
_rulebook_query_spec.loader.exec_module(_rulebook_query_module)
create_rulebook_query = _rulebook_query_module.create_rulebook_query
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from src.ptcg_ai.referee import RefereeAgent as BaseRefereeAgent
from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent
from src.ptcg_ai.rulebook import RuleKnowledgeBase
from src.ptcg_ai.simulation import load_rulebook_text, build_deck
from src.ptcg_ai.models import Zone
from typing import Union

# Try to import ChatZhipuAI for GLM-4.6 support
try:
    from langchain_community.chat_models import ChatZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    ChatZhipuAI = None


# 全局日志文件对象
_log_file = None
_log_file_path = None


def setup_logging(log_dir: Path = None) -> Path:
    """设置日志文件。
    
    Args:
        log_dir: 日志文件目录，如果为None则使用项目根目录下的logs目录
    
    Returns:
        日志文件路径
    """
    global _log_file, _log_file_path
    
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"
    else:
        log_dir = Path(log_dir)
    
    # 创建logs目录
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成日志文件名（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = log_dir / f"game_{timestamp}.log"
    
    # 打开日志文件
    _log_file = open(log_file_path, "w", encoding="utf-8")
    _log_file_path = log_file_path
    
    # 配置 Python logging 模块，将日志也输出到文件和控制台
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return log_file_path


def log_print(*args, **kwargs):
    """同时打印到控制台和日志文件。
    
    Args:
        *args: 要打印的参数
        **kwargs: print函数的其他参数（如end, sep等）
    """
    # 打印到控制台
    print(*args, **kwargs)
    
    # 写入日志文件
    if _log_file is not None:
        # 将参数转换为字符串
        message = " ".join(str(arg) for arg in args)
        if "end" in kwargs and kwargs["end"] != "\n":
            _log_file.write(message + kwargs["end"])
        else:
            _log_file.write(message + "\n")
        _log_file.flush()  # 立即刷新到文件


def close_logging():
    """关闭日志文件。"""
    global _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None


def create_llm(model_type: str = "openai"):
    """Create a LangChain LLM instance based on model type.

    Args:
        model_type: One of "openai", "openai-cheap", "anthropic", or "glm-4"

    Returns:
        LangChain chat model instance
    """
    if model_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return ChatOpenAI(model="gpt-5", temperature=0)
    elif model_type == "openai-cheap":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    elif model_type == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        return ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0)
    elif model_type == "glm-4":
        if not ZHIPU_AVAILABLE:
            raise ImportError(
                "ChatZhipuAI is not available. Install it with: pip install langchain-community"
            )
        # ChatZhipuAI uses ZHIPUAI_API_KEY (not ZHIPU_API_KEY)
        api_key = os.getenv("ZHIPUAI_API_KEY")
        if not api_key:
            return None
        return ChatZhipuAI(model="glm-4", temperature=0, zhipuai_api_key=api_key)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def print_player_state(referee: BaseRefereeAgent, player_id: str, title: str = ""):
    """打印玩家的详细状态信息。
    
    Args:
        referee: RefereeAgent 实例
        player_id: 玩家ID
        title: 可选的标题前缀
    """
    from src.ptcg_ai.models import Zone
    
    player_state = referee.state.players[player_id]
    hand = player_state.zone(Zone.HAND)
    active = player_state.zone(Zone.ACTIVE)
    bench = player_state.zone(Zone.BENCH)
    deck = player_state.zone(Zone.DECK)
    discard = player_state.zone(Zone.DISCARD)
    
    prefix = f"  [{title}] " if title else "  "
    
    log_print(f"\n{prefix}{player_id} 的状态:")
    log_print(f"  牌库: {len(deck.cards)} 张 | 奖赏卡: {player_state.prizes_remaining} 张 | 弃牌区: {len(discard.cards)} 张")
    
    # 手牌信息
    log_print(f"  手牌 ({len(hand.cards)} 张):")
    if hand.cards:
        # 按类型分组统计
        hand_by_type = {}
        for card in hand.cards:
            card_type = card.definition.card_type
            card_name = card.definition.name
            if card_type not in hand_by_type:
                hand_by_type[card_type] = []
            hand_by_type[card_type].append(card_name)
        
        for card_type, names in sorted(hand_by_type.items()):
            # 统计每种卡的数量
            card_counts = Counter(names)
            card_list = [f"{name} x{count}" if count > 1 else name for name, count in card_counts.items()]
            log_print(f"    {card_type}: {', '.join(card_list)}")
    else:
        log_print("    (空)")
    
    # 战斗区信息
    log_print(f"  战斗区:")
    if active.cards:
        for card in active.cards:
            card_info = f"    {card.definition.name}"
            if card.definition.card_type == "Pokemon":
                hp = card.hp or 0
                damage = card.damage
                remaining_hp = max(0, hp - damage) if hp else 0
                card_info += f" (HP: {remaining_hp}/{hp}"
                if damage > 0:
                    card_info += f", 伤害: {damage}"
                card_info += ")"
                if card.special_conditions:
                    card_info += f" [状态: {', '.join(card.special_conditions)}]"
                if card.attached_energy:
                    card_info += f" [能量: {len(card.attached_energy)}]"
            else:
                card_info += f" ({card.definition.card_type})"
            log_print(card_info)
    else:
        log_print("    (空)")
    
    # 备战区信息
    log_print(f"  备战区 ({len(bench.cards)} 张):")
    if bench.cards:
        for i, card in enumerate(bench.cards, 1):
            card_info = f"    [{i}] {card.definition.name}"
            if card.definition.card_type == "Pokemon":
                hp = card.hp or 0
                damage = card.damage
                remaining_hp = max(0, hp - damage) if hp else 0
                card_info += f" (HP: {remaining_hp}/{hp}"
                if damage > 0:
                    card_info += f", 伤害: {damage}"
                card_info += ")"
                if card.special_conditions:
                    card_info += f" [状态: {', '.join(card.special_conditions)}]"
                if card.attached_energy:
                    card_info += f" [能量: {len(card.attached_energy)}]"
            else:
                card_info += f" ({card.definition.card_type})"
            log_print(card_info)
    else:
        log_print("    (空)")


def run_full_game(referee: BaseRefereeAgent, players: dict[str, Union[BasePlayerAgent, PlayerAgentSDK]], use_sdk: bool = False, llm=None, test_mode: bool = False):
    """运行完整的游戏流程：从准备阶段到胜负判定。
    
    Args:
        referee: RefereeAgent 实例
        players: 玩家ID到PlayerAgent的映射
        use_sdk: 是否使用LangChain SDK
        llm: LangChain LLM实例（如果use_sdk=True）
        test_mode: 如果为True，在第一个回合的主阶段结束后停止
    """
    from src.ptcg_ai.models import Zone
    from src.ptcg_ai.referee import OperationRequest, OperationResult
    
    # 如果使用 SDK，提前创建一次
    referee_sdk = None
    if use_sdk and llm:
        referee_sdk = RefereeAgentSDK(referee, llm)
    
    log_print("\n" + "="*60)
    log_print("游戏开始！")
    log_print("="*60)
    
    # ============================================================
    # 阶段1: 游戏准备阶段
    # ============================================================
    log_print("\n【阶段1: 游戏准备】")
    
    # 1.1 先决定先后手的顺序
    referee._determine_starting_player()
    starting_player = referee.state.turn_player
    log_print(f"  先手玩家: {starting_player} (通过投硬币决定)")
    
    # 1.2 双方充分洗牌（如果初始化时已经放置了奖赏卡，需要先洗回牌库）
    for player_id in players.keys():
        prize_zone = referee.state.players[player_id].zone(Zone.PRIZE)
        deck = referee.state.players[player_id].zone(Zone.DECK)
        
        # 如果奖赏卡已经放置了（初始化时），先洗回牌库
        if prize_zone.cards:
            deck.cards.extend(prize_zone.cards)
            prize_zone.cards.clear()
            log_print(f"  {player_id}: 将初始化时放置的奖赏卡洗回牌库")
        
        referee.tools.shuffle(player_id, Zone.DECK)
        log_print(f"  {player_id}: 洗牌完成")
    
    # 1.2.1 双方抽起始手牌（7张）
    for player_id in players.keys():
        drawn = referee.tools.draw(player_id, 7)
        log_print(f"  {player_id}: 抽起始手牌 {len(drawn)} 张")
        print_player_state(referee, player_id, "抽起始手牌后")
    
    # 1.3 准备阶段：每个玩家需要放置基础宝可梦到战斗区
    player_ids = list(players.keys())
    setup_complete = {player_id: False for player_id in player_ids}
    
    while not all(setup_complete.values()):
        # 检查哪些玩家还没有完成准备
        incomplete_players = [pid for pid in player_ids if not setup_complete[pid]]
        
        # 先检查每个玩家是否有基础宝可梦
        players_without_basic = []
        for player_id in incomplete_players:
            hand = referee.state.players[player_id].zone(Zone.HAND)
            active = referee.state.players[player_id].zone(Zone.ACTIVE)
            
            # 如果已经有战斗区宝可梦，说明已经完成准备
            if active.cards:
                setup_complete[player_id] = True
                continue
            
            # 检查手牌中的基础宝可梦
            basic_pokemon = [
                card for card in hand.cards
                if card.definition.card_type == "Pokemon" and card.definition.stage == "Basic"
            ]
            
            if not basic_pokemon:
                # 没有基础宝可梦，需要重新抽牌
                players_without_basic.append(player_id)
        
        # 如果有玩家没有基础宝可梦，需要重新抽牌
        if players_without_basic:
            # 如果双方都没有基础宝可梦，双方都重新抽牌（没有额外抽牌）
            if len(players_without_basic) == 2:
                log_print(f"\n  双方都没有基础宝可梦，双方都重新抽牌")
                for player_id in players_without_basic:
                    hand = referee.state.players[player_id].zone(Zone.HAND)
                    if hand.cards:
                        referee.tools.shuffle_hand_into_deck(player_id)
                        log_print(f"    {player_id}: 将手牌洗回牌库")
                    drawn = referee.tools.draw(player_id, 7)
                    log_print(f"    {player_id}: 重新抽7张牌")
                    print_player_state(referee, player_id, "重新抽牌后")
            else:
                # 只有一个玩家没有基础宝可梦，该玩家重新抽牌，对手可以抽一张
                for player_id in players_without_basic:
                    hand = referee.state.players[player_id].zone(Zone.HAND)
                    if hand.cards:
                        referee.tools.shuffle_hand_into_deck(player_id)
                        log_print(f"\n  {player_id}: 没有基础宝可梦，将手牌洗回牌库")
                    
                    drawn = referee.tools.draw(player_id, 7)
                    log_print(f"  {player_id}: 重新抽7张牌")
                    print_player_state(referee, player_id, "重新抽牌后")
                    
                    # 对手可以抽一张牌
                    opponent_id = [pid for pid in player_ids if pid != player_id][0]
                    if not setup_complete[opponent_id]:  # 只有对手也还没完成时才抽牌
                        drawn_opponent = referee.tools.draw(opponent_id, 1)
                        log_print(f"  {opponent_id}: 对手重新抽牌，额外抽1张牌")
        
        # 检查每个玩家是否有基础宝可梦并完成放置
        for player_id in incomplete_players:
            hand = referee.state.players[player_id].zone(Zone.HAND)
            active = referee.state.players[player_id].zone(Zone.ACTIVE)
            
            # 如果已经有战斗区宝可梦，跳过
            if active.cards:
                setup_complete[player_id] = True
                continue
            
            # 检查手牌中的基础宝可梦
            basic_pokemon = [
                card for card in hand.cards
                if card.definition.card_type == "Pokemon" and card.definition.stage == "Basic"
            ]
            
            if basic_pokemon:
                # 有基础宝可梦，需要放置到战斗区
                # 选择第一张基础宝可梦放到战斗区
                active_pokemon = basic_pokemon[0]
                referee.tools.move_card(player_id, Zone.HAND, Zone.ACTIVE, active_pokemon)
                log_print(f"\n  {player_id}: 放置基础宝可梦到战斗区: {active_pokemon.definition.name}")
                
                # 可以放置更多基础宝可梦到备战区（最多5张）
                bench = referee.state.players[player_id].zone(Zone.BENCH)
                remaining_basic = [p for p in basic_pokemon[1:] if p.uid != active_pokemon.uid]
                
                for bench_pokemon in remaining_basic[:5 - len(bench.cards)]:
                    referee.tools.move_card(player_id, Zone.HAND, Zone.BENCH, bench_pokemon)
                    log_print(f"  {player_id}: 放置基础宝可梦到备战区: {bench_pokemon.definition.name}")
                
                # 放置奖赏卡（6张）- 从牌库顶部取6张
                # 注意：如果初始化时已经放置了奖赏卡，需要先清空
                deck = referee.state.players[player_id].zone(Zone.DECK)
                prize_zone = referee.state.players[player_id].zone(Zone.PRIZE)
                
                # 如果奖赏卡已经放置了（初始化时），先清空
                if prize_zone.cards:
                    # 将已放置的奖赏卡洗回牌库
                    deck.cards.extend(prize_zone.cards)
                    prize_zone.cards.clear()
                    referee.tools.shuffle(player_id, Zone.DECK)
                
                # 确保牌库有足够的卡
                if len(deck.cards) >= 6:
                    prize_zone.cards[:] = deck.cards[:6]
                    del deck.cards[:6]
                    log_print(f"  {player_id}: 放置6张奖赏卡")
                else:
                    log_print(f"  ⚠️ {player_id}: 牌库不足6张，无法放置奖赏卡")
                
                setup_complete[player_id] = True
                print_player_state(referee, player_id, "准备完成")
    
    log_print("\n  ✓ 所有玩家完成准备阶段")
    
    # 1.4 先手玩家抽1张卡（游戏正式开始）
    if starting_player:
        drawn = referee.tools.draw(starting_player, 1)
        log_print(f"\n  {starting_player} 抽1张卡开始游戏")
        print_player_state(referee, starting_player, "先手抽卡后")
    
    # ============================================================
    # 阶段2: 游戏主循环
    # ============================================================
    log_print("\n" + "="*60)
    log_print("【阶段2: 游戏主循环】")
    log_print("="*60)
    
    max_turns = 50  # 防止无限循环
    turn_count = 0
    first_main_phase_completed = False  # 跟踪第一个主阶段是否完成（用于测试模式）
    
    while turn_count < max_turns:
        turn_count += 1
        current_player = referee.state.turn_player
        
        if current_player is None:
            log_print("\n错误: 当前没有活跃玩家")
            break
        
        log_print(f"\n--- 回合 {referee.state.turn_number} - {current_player} 的回合 ---")
        
        # 显示回合开始前的状态
        print_player_state(referee, current_player, "回合开始前")
        
        # 2.1 开始回合（抽1张卡）
        try:
            turn_result = referee.start_turn(current_player)
            log_print(f"  {turn_result['message']}")
            if 'drawn' in turn_result and turn_result['drawn']:
                # 获取抽到的卡牌信息
                drawn_card_uid = turn_result['drawn'][0]
                hand = referee.state.players[current_player].zone(Zone.HAND)
                drawn_card = next((c for c in hand.cards if c.uid == drawn_card_uid), None)
                if drawn_card:
                    log_print(f"  抽到卡: {drawn_card.definition.name} ({drawn_card.definition.card_type})")
                else:
                    log_print(f"  抽到卡: {drawn_card_uid}")
            
            # 显示抽卡后的状态
            print_player_state(referee, current_player, "抽卡后")
        except Exception as e:
            log_print(f"  ✗ 开始回合失败: {e}")
            break
        
        # 2.2 主阶段：玩家可以进行多次操作
        log_print(f"\n  【主阶段】")
        main_phase_actions = 0
        max_main_actions = 10  # 限制主阶段操作次数，防止无限循环
        consecutive_errors = 0  # 连续错误计数
        max_consecutive_errors = 2  # 最多允许2次连续错误
        last_error_message = None  # 上一次操作的错误消息
        
        while main_phase_actions < max_main_actions:
            # 获取当前玩家状态
            player_state = referee.state.players[current_player]
            hand = player_state.zone(Zone.HAND)
            active = player_state.zone(Zone.ACTIVE)
            bench = player_state.zone(Zone.BENCH)
            discard = player_state.zone(Zone.DISCARD)
            hand_size = len(hand.cards)
            deck_size = len(player_state.zone(Zone.DECK).cards)
            prizes = player_state.prizes_remaining
            
            # 获取对手信息
            opponent_id = [pid for pid in referee.state.players.keys() if pid != current_player][0]
            opponent_state = referee.state.players[opponent_id]
            opponent_hand = opponent_state.zone(Zone.HAND)
            opponent_active = opponent_state.zone(Zone.ACTIVE)
            opponent_bench = opponent_state.zone(Zone.BENCH)
            opponent_discard = opponent_state.zone(Zone.DISCARD)
            
            # PlayerAgent 做出决策
            player = players[current_player]
            
            # 构建详细的观察信息（供AI模型决策使用）
            observation = {
                "turn_number": referee.state.turn_number,
                "phase": referee.state.phase,
                
                # 自己的信息
                "my_hand_size": hand_size,
                "my_prizes": prizes,
                "my_deck_size": deck_size,
                "my_discard_size": len(discard.cards),
                # 自己的手牌信息（包含UID，这是最重要的！）
                "my_hand_cards": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "type": card.definition.card_type,
                        "stage": card.definition.stage,
                        "hp": card.definition.hp if card.definition.card_type == "Pokemon" else None,
                        "subtypes": card.definition.subtypes or [],
                        "rules_text": card.definition.rules_text or "",  # 卡牌效果文本，非常重要！
                        "abilities": card.definition.abilities or [],  # 宝可梦的能力
                        "attacks": card.definition.attacks or [],  # 宝可梦的攻击
                    }
                    for card in hand.cards
                ],
                # 自己的战斗区和备战区信息
                "my_active_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "attacks": card.definition.attacks or [],
                        "abilities": card.definition.abilities or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in active.cards
                ],
                "my_bench_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "attacks": card.definition.attacks or [],
                        "abilities": card.definition.abilities or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in bench.cards
                ],
                "my_bench_count": len(bench.cards),
                # 自己的弃牌区信息（最近弃掉的卡牌，用于了解游戏历史）
                "my_discard_pile": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "type": card.definition.card_type,
                    }
                    for card in discard.cards[-10:]  # 只显示最近10张，避免信息过载
                ],
                
                # 对手的信息（公开信息）
                "opponent_hand_size": len(opponent_hand.cards),
                "opponent_prizes": opponent_state.prizes_remaining,
                "opponent_deck_size": len(opponent_state.zone(Zone.DECK).cards),
                "opponent_discard_size": len(opponent_discard.cards),
                # 对手的战斗区和备战区信息（公开可见）
                "opponent_active_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "attacks": card.definition.attacks or [],
                        "abilities": card.definition.abilities or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in opponent_active.cards
                ],
                "opponent_bench_pokemon": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "hp": card.hp,
                        "max_hp": card.definition.hp,
                        "damage": card.damage,
                        "attached_energy_count": len(card.attached_energy),
                        "attacks": card.definition.attacks or [],
                        "abilities": card.definition.abilities or [],
                        "special_conditions": card.special_conditions or [],
                    }
                    for card in opponent_bench.cards
                ],
                "opponent_bench_count": len(opponent_bench.cards),
                # 对手的弃牌区信息（公开可见）
                "opponent_discard_pile": [
                    {
                        "uid": card.uid,
                        "name": card.definition.name,
                        "type": card.definition.card_type,
                    }
                    for card in opponent_discard.cards[-10:]  # 只显示最近10张
                ],
            }
            
            # 如果有上一次操作的错误消息，添加到观察信息中
            if last_error_message:
                observation["last_action_error"] = last_error_message
                observation["last_action_failed"] = True
                log_print(f"    ℹ️ 上一次操作失败: {last_error_message}")
            else:
                observation["last_action_failed"] = False
            
            # 如果使用 SDK（AI 模型），使用 invoke 方法；否则使用 decide 方法
            reasoning_messages = None
            if isinstance(player, PlayerAgentSDK):
                # 打印观察信息摘要
                log_print(f"\n  【{current_player} 的观察信息摘要】")
                log_print(f"    手牌数量: {len(observation.get('my_hand_cards', []))}")
                log_print(f"    战斗区宝可梦: {len(observation.get('my_active_pokemon', []))}")
                log_print(f"    备战区宝可梦: {len(observation.get('my_bench_pokemon', []))}")
                if observation.get('my_hand_cards'):
                    hand_names = [card.get('name', 'unknown') for card in observation.get('my_hand_cards', [])[:5]]
                    log_print(f"    手牌前5张: {', '.join(hand_names)}")
                
                request, reasoning_messages = player.invoke(observation, return_reasoning=True)
                
                # 打印推理过程
                if reasoning_messages:
                    log_print(f"\n  【{current_player} 的推理过程】")
                    for i, msg in enumerate(reasoning_messages, 1):
                        msg_type = type(msg).__name__
                        if hasattr(msg, "content") and msg.content:
                            content = str(msg.content)
                            # 限制内容长度，避免输出过长
                            if len(content) > 1000:
                                content = content[:1000] + "... (内容过长，已截断)"
                            log_print(f"    [{i}] {msg_type}: {content}")
                        elif hasattr(msg, "tool_calls") and msg.tool_calls:
                            tool_names = []
                            for tc in msg.tool_calls:
                                if isinstance(tc, dict):
                                    tool_names.append(tc.get('name', 'unknown'))
                                else:
                                    tool_names.append(getattr(tc, 'name', 'unknown'))
                            log_print(f"    [{i}] {msg_type}: 工具调用 - {tool_names}")
                            # 打印工具调用的参数
                            for tc in msg.tool_calls:
                                if isinstance(tc, dict):
                                    args = tc.get('args', {})
                                    # Also check for 'arguments' key (some LangChain versions use this)
                                    if not args and 'arguments' in tc:
                                        args_str = tc.get('arguments')
                                        if isinstance(args_str, str):
                                            try:
                                                import json
                                                args = json.loads(args_str)
                                            except:
                                                args = args_str
                                    log_print(f"        参数: {args}")
                                    # For decide_action, also log payload specifically
                                    if tc.get('name') == 'decide_action' and isinstance(args, dict):
                                        payload = args.get('payload')
                                        log_print(f"        payload值: {payload}, 类型: {type(payload)}")
                                elif hasattr(tc, 'args'):
                                    args = tc.args
                                    log_print(f"        参数: {args}")
                                    # For decide_action, also log payload specifically
                                    if getattr(tc, 'name', None) == 'decide_action' and isinstance(args, dict):
                                        payload = args.get('payload')
                                        log_print(f"        payload值: {payload}, 类型: {type(payload)}")
                                elif hasattr(tc, 'arguments'):
                                    # Some LangChain versions store arguments as a JSON string
                                    args_str = getattr(tc, 'arguments', '{}')
                                    if isinstance(args_str, str):
                                        try:
                                            import json
                                            args = json.loads(args_str)
                                            log_print(f"        参数(从arguments解析): {args}")
                                        except:
                                            log_print(f"        参数(原始arguments): {args_str}")
                        else:
                            log_print(f"    [{i}] {msg_type}: {str(msg)[:200]}")
            else:
                request = player.decide(observation)
            
            if request is None:
                # 玩家决定结束回合
                log_print(f"\n  ⚠️ {current_player} 决定结束回合（未生成任何操作请求）")
                if reasoning_messages:
                    log_print(f"  【调试信息】最后一条消息:")
                    last_msg = reasoning_messages[-1] if reasoning_messages else None
                    if last_msg:
                        if hasattr(last_msg, "content") and last_msg.content:
                            log_print(f"    内容: {str(last_msg.content)[:500]}")
                        elif hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                            log_print(f"    工具调用: {[getattr(tc, 'name', 'unknown') for tc in last_msg.tool_calls]}")
                        else:
                            log_print(f"    原始: {str(last_msg)[:500]}")
                log_print(f"  ⚠️ 如果这不应该发生，请检查:")
                log_print(f"     1. LLM 是否正确响应")
                log_print(f"     2. 观察信息是否完整")
                log_print(f"     3. instructions 是否过于复杂导致 LLM 困惑")
                break
            
            # 处理玩家请求
            try:
                # 判断请求类型：自然语言字符串还是 OperationRequest
                if isinstance(request, str):
                    # 自然语言请求
                    log_print(f"\n  {current_player} 提出请求: {request}")
                    
                    # 使用 RefereeAgentSDK 处理自然语言请求
                    if referee_sdk:
                        result = referee.handle_natural_language_request(current_player, request, referee_sdk)
                    else:
                        # 如果没有 SDK，创建临时 SDK 来处理
                        if llm:
                            temp_referee_sdk = RefereeAgentSDK(referee, llm)
                            result = referee.handle_natural_language_request(current_player, request, temp_referee_sdk)
                        else:
                            result = OperationResult(False, "需要 LLM 来处理自然语言请求")
                else:
                    # 结构化请求 (OperationRequest)
                    log_print(f"\n  {current_player} 执行操作: {request.action}")
                    if request.payload:
                        log_print(f"    参数: {request.payload}")
                    
                    # 使用基础 RefereeAgent 处理结构化请求
                    result = referee.handle_request(request)
                
                # 打印 referee 的完整反馈
                log_print(f"\n  【Referee 反馈】")
                log_print(f"    结果: {result.message}")
                if hasattr(result, 'data') and result.data:
                    log_print(f"    数据: {result.data}")
                if not result.success:
                    log_print(f"    ⚠️ 操作失败")
                else:
                    log_print(f"    ✓ 操作成功")
                
                # 检查是否需要玩家选择
                if result.requires_selection and result.candidates:
                    log_print(f"\n  ⚠️ 需要玩家选择，候选数量: {len(result.candidates)}")
                    # 显示候选列表
                    candidate_list = []
                    for candidate in result.candidates:
                        candidate_str = f"{candidate.get('name', 'Unknown')}(uid:{candidate.get('uid', 'unknown')})"
                        candidate_list.append(candidate_str)
                    log_print(f"    候选列表: {', '.join(candidate_list)}")
                    
                    # 进入选择循环
                    selection_made = False
                    max_selection_attempts = 3
                    selection_attempts = 0
                    
                    while not selection_made and selection_attempts < max_selection_attempts:
                        selection_attempts += 1
                        
                        # 构建包含候选列表的观察信息
                        selection_observation = observation.copy()
                        selection_observation["requires_selection"] = True
                        selection_observation["candidates"] = result.candidates
                        selection_observation["selection_message"] = result.message
                        selection_observation["selection_context"] = result.selection_context
                        
                        # Player做出选择
                        if isinstance(player, PlayerAgentSDK):
                            selection_request, _ = player.invoke(selection_observation, return_reasoning=False)
                        else:
                            selection_request = player.decide(selection_observation)
                        
                        if not selection_request:
                            log_print(f"    ⚠️ Player未做出选择，结束选择循环")
                            break
                        
                        log_print(f"\n  {current_player} 做出选择: {selection_request}")
                        
                        # Referee处理选择
                        if referee_sdk:
                            selection_result = referee.handle_player_selection(
                                current_player,
                                selection_request,
                                result.selection_context or {},
                                referee_sdk
                            )
                        else:
                            if llm:
                                temp_referee_sdk = RefereeAgentSDK(referee, llm)
                                selection_result = referee.handle_player_selection(
                                    current_player,
                                    selection_request,
                                    result.selection_context or {},
                                    temp_referee_sdk
                                )
                            else:
                                selection_result = OperationResult(False, "需要 LLM 来处理选择请求")
                        
                        log_print(f"    选择结果: {selection_result.message}")
                        
                        if selection_result.success:
                            selection_made = True
                            result = selection_result  # 使用选择结果作为最终结果
                            break
                        else:
                            log_print(f"    ⚠️ 选择失败: {selection_result.message}")
                            if selection_attempts < max_selection_attempts:
                                log_print(f"    ℹ️ 重试选择 ({selection_attempts}/{max_selection_attempts})...")
                    
                    if not selection_made:
                        log_print(f"    ⚠️ 选择失败或超时，结束主阶段")
                        break
                
                if not result.success:
                    log_print(f"    ⚠️ 操作失败: {result.message}")
                    last_error_message = result.message  # 保存错误消息供下次观察使用
                    consecutive_errors += 1
                    
                    # 如果连续错误次数过多，结束主阶段
                    if consecutive_errors >= max_consecutive_errors:
                        log_print(f"    ⚠️ 连续{consecutive_errors}次操作失败，结束主阶段")
                        break
                    
                    # 参数错误时，允许重试（但有限制）
                    if "requires" in result.message.lower() or "parameter" in result.message.lower() or "invalid parameter" in result.message.lower() or "trainer_card" in result.message.lower() or "缺少" in result.message or "需要" in result.message:
                        log_print(f"    ℹ️ 参数错误，允许重试（{consecutive_errors}/{max_consecutive_errors}）...")
                        log_print(f"    💡 提示：请检查观察信息中的hand_cards，使用卡牌的uid字段，而不是卡牌名称")
                        continue  # 继续循环，让AI看到错误消息后重试
                    else:
                        # 规则违反或其他错误，结束主阶段
                        log_print(f"    ⚠️ 规则违反，结束主阶段")
                        break
                
                # 显示操作后的状态
                action_name = request.action if hasattr(request, 'action') else "自然语言请求"
                print_player_state(referee, current_player, f"操作后 ({action_name})")
                
                # 操作成功，重置错误计数和错误消息
                consecutive_errors = 0
                last_error_message = None
                main_phase_actions += 1
                
                # 检查胜负条件
                winner = referee.check_win_condition()
                if winner:
                    log_print(f"\n  🎉 游戏结束！获胜者: {winner}")
                    return winner
                    
            except Exception as e:
                log_print(f"  ✗ 处理操作时出错: {e}")
                # 出错时结束主阶段
                break
        
        # 2.3 结束回合
        try:
            # 显示回合结束前的状态
            print_player_state(referee, current_player, "回合结束前")
            
            end_result = referee.end_turn(current_player)
            log_print(f"\n  {end_result['message']}")
            
            # 测试模式：第一个玩家的主阶段结束后停止
            if test_mode and not first_main_phase_completed:
                first_main_phase_completed = True
                log_print(f"\n  【测试模式】第一个玩家({current_player})的主阶段已结束，停止游戏")
                return None
            
            # 显示回合结束后的状态（下一个玩家的状态）
            next_player = end_result.get('next_player')
            if next_player:
                print_player_state(referee, next_player, "回合切换后")
            
            # 再次检查胜负条件
            winner = referee.check_win_condition()
            if winner:
                log_print(f"\n  🎉 游戏结束！获胜者: {winner}")
                return winner
                
        except Exception as e:
            log_print(f"  ✗ 结束回合失败: {e}")
            break
    
    # 如果达到最大回合数
    if turn_count >= max_turns:
        log_print(f"\n  ⚠️ 达到最大回合数限制 ({max_turns})，游戏结束")
    
    # 最终胜负判定
    winner = referee.check_win_condition()
    if winner:
        log_print(f"\n  🎉 游戏结束！获胜者: {winner}")
    else:
        log_print(f"\n  ⚠️ 游戏结束，但未决出胜负")
    
    return winner


def main():
    """完整游戏流程演示：从准备阶段到胜负判定。"""
    # 设置日志
    log_file_path = setup_logging()
    log_print(f"日志文件: {log_file_path}")
    log_print("="*60)
    
    try:
        # 加载规则书
        rulebook_path = Path("doc/rulebook_extracted.txt")
        if rulebook_path.exists():
            rulebook = load_rulebook_text(rulebook_path)
        else:
            # 创建最小规则书用于演示
            rulebook = RuleKnowledgeBase.from_text("1 测试规则。")

        # 从文件加载卡组
        deck_file = Path("doc/deck/deck1.txt")
        if not deck_file.exists():
            log_print(f"错误：找不到卡组文件 {deck_file}")
            log_print("请确保 doc/deck/deck1.txt 文件存在。")
            return

        try:
            log_print(f"正在从 {deck_file} 加载卡组...")
            deck_a = build_deck("playerA", deck_file)
            deck_b = build_deck("playerB", deck_file)
            log_print(f"✓ 成功加载两个玩家的卡组（每个60张卡）")
        except Exception as e:
            log_print(f"✗ 加载卡组失败: {e}")
            return

        # 创建基础 Referee Agent
        base_referee = BaseRefereeAgent.create(
            match_id="demo-001",
            player_decks={"playerA": deck_a, "playerB": deck_b},
            knowledge_base=rulebook,
        )

        log_print("✓ 基础 RefereeAgent 创建成功！")
        log_print(f"  对局ID: {base_referee.state.match_id}")
        log_print(f"  玩家: {list(base_referee.state.players.keys())}")

        # 尝试创建 LLM（按优先级：GLM-4.6 > OpenAI > Anthropic）
        llm = None
        model_type = None
        use_sdk = False
        
        if os.getenv("ZHIPUAI_API_KEY") and ZHIPU_AVAILABLE:
            llm = create_llm("glm-4")
            model_type = "智谱AI GLM-4.6"
            use_sdk = True
        elif os.getenv("OPENAI_API_KEY"):
            llm = create_llm("openai")
            model_type = "OpenAI GPT-5"
            use_sdk = True
        elif os.getenv("ANTHROPIC_API_KEY"):
            llm = create_llm("anthropic")
            model_type = "Anthropic Claude 3.5 Sonnet"
            use_sdk = True
        
        # 创建 Player Agents（如果使用 SDK，则创建 PlayerAgentSDK；否则使用 BasePlayerAgent）
        if use_sdk and llm:
            log_print(f"\n使用 LangChain Agents ({model_type})")
            # 创建 rulebook_query 用于查询 advanced-manual-split
            rulebook_query = create_rulebook_query()
            # 为每个玩家创建 PlayerAgentSDK，传入 knowledge_base 和 rulebook_query 以便查询规则
            players = {
                "playerA": PlayerAgentSDK(BasePlayerAgent("playerA"), llm, strategy="balanced", knowledge_base=rulebook, rulebook_query=rulebook_query),
                "playerB": PlayerAgentSDK(BasePlayerAgent("playerB"), llm, strategy="balanced", knowledge_base=rulebook, rulebook_query=rulebook_query),
            }
            log_print("✓ PlayerAgentSDK 创建成功（使用 AI 模型进行决策）")
        else:
            log_print("\n使用基础 PlayerAgent（不使用 LangChain SDK）")
            log_print("提示: 设置 API key 可使用 LangChain Agents 和 AI 模型决策")
            log_print("  - ZHIPUAI_API_KEY (推荐，使用 GLM-4.6)")
            log_print("  - OPENAI_API_KEY (使用 GPT-5)")
            log_print("  - ANTHROPIC_API_KEY (使用 Claude 3.5)")
            # 使用基础 PlayerAgent（决策逻辑简单）
            players = {
                "playerA": BasePlayerAgent("playerA"),
                "playerB": BasePlayerAgent("playerB"),
            }

        # 运行完整游戏
        try:
            # 测试模式：在第一个回合的主阶段结束后停止，并打印推理过程
            test_mode = False  # 设置为False以关闭测试模式，运行完整游戏
            
            winner = run_full_game(base_referee, players, use_sdk=use_sdk, llm=llm, test_mode=test_mode)
            
            # 输出游戏统计
            log_print("\n" + "="*60)
            log_print("【游戏统计】")
            log_print("="*60)
            for player_id in players.keys():
                print_player_state(base_referee, player_id, "最终状态")
            
            if winner:
                log_print(f"\n🏆 最终获胜者: {winner}")
            else:
                log_print(f"\n⚠️ 游戏未决出胜负")
                
        except Exception as e:
            log_print(f"\n✗ 游戏运行出错: {e}")
            import traceback
            traceback.print_exc()
    finally:
        # 关闭日志文件
        close_logging()
        if log_file_path:
            print(f"\n日志已保存到: {log_file_path}")


if __name__ == "__main__":
    main()
