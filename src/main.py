"""Example script demonstrating LangChain Agents integration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to Python path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agents.referee import RefereeAgentSDK
from agents.players import PlayerAgentSDK
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from src.ptcg_ai.referee import RefereeAgent as BaseRefereeAgent
from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent
from src.ptcg_ai.rulebook import RuleKnowledgeBase
from src.ptcg_ai.simulation import load_rulebook_text, build_deck

# Try to import ChatZhipuAI for GLM-4.6 support
try:
    from langchain_community.chat_models import ChatZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    ChatZhipuAI = None


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
        return ChatOpenAI(model="gpt-4o", temperature=0)
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


def main():
    """示例脚本：演示 LangChain Agents 集成。"""
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
        print(f"错误：找不到卡组文件 {deck_file}")
        print("请确保 doc/deck/deck1.txt 文件存在。")
        return

    try:
        print(f"正在从 {deck_file} 加载卡组...")
        deck_a = build_deck("playerA", deck_file)
        deck_b = build_deck("playerB", deck_file)
        print(f"✓ 成功加载两个玩家的卡组（每个60张卡）")
    except Exception as e:
        print(f"✗ 加载卡组失败: {e}")
        return

    # Create base Referee Agent
    base_referee = BaseRefereeAgent.create(
        match_id="demo-001",
        player_decks={"playerA": deck_a, "playerB": deck_b},
        knowledge_base=rulebook,
    )

    print("✓ 基础 RefereeAgent 创建成功！")
    print(f"  对局ID: {base_referee.state.match_id}")
    print(f"  玩家: {list(base_referee.state.players.keys())}")

    # 尝试创建 LLM（按优先级：GLM-4 > OpenAI > Anthropic）
    llm = None
    model_type = "智谱AI GLM-4.6"
    if os.getenv("ZHIPUAI_API_KEY") and ZHIPU_AVAILABLE:
        llm = create_llm("glm-4")
        model_type = "智谱AI GLM-4.6"
    elif os.getenv("OPENAI_API_KEY"):
        llm = create_llm("openai")
        model_type = "OpenAI GPT-4o"
    elif os.getenv("ANTHROPIC_API_KEY"):
        llm = create_llm("anthropic")
        model_type = "Anthropic Claude 3.5 Sonnet"
    else:
        print("\n" + "="*60)
        print("LangChain Agents 演示（已跳过）")
        print("="*60)
        print("未设置 API key，跳过 SDK 集成演示。")
        print("\n要使用 LangChain Agents，请设置以下环境变量之一：")
        print("  1. ZHIPUAI_API_KEY（GLM-4.6，默认推荐）：")
        print("     export ZHIPUAI_API_KEY='your-api-key'")
        print("     # 需要安装: pip install langchain-community")
        print("  2. OPENAI_API_KEY：")
        print("     export OPENAI_API_KEY='your-api-key'")
        print("  3. ANTHROPIC_API_KEY：")
        print("     export ANTHROPIC_API_KEY='your-api-key'")
        print("  4. 再次运行此脚本")
        print("\n基础 RefereeAgent（不使用 SDK）可以在没有 API key 的情况下工作。")
        return

    # 包装为 LangChain SDK 版本
    print("\n" + "="*60)
    print(f"LangChain Agents 演示（使用 {model_type}）")
    print("="*60)

    try:
        # 创建 LangChain Referee Agent
        referee_sdk = RefereeAgentSDK(base_referee, llm)

        # 使用 LangChain 原生接口 invoke()
        print("\n正在处理玩家请求：抽1张卡...")
        result = referee_sdk.invoke({
            "input": {
                "player_id": "playerA",
                "action": "draw",
                "payload": {"count": 1}
            },
            "chat_history": []
        })

        print(f"✓ 结果: {result}")

        # 演示多模型支持
        print("\n" + "-"*60)
        print("多模型支持示例")
        print("-"*60)
        print("LangChain 支持多种模型后端：")
        print("  - OpenAI: ChatOpenAI(model='gpt-4o')")
        print("  - Anthropic: ChatAnthropic(model='claude-3-5-sonnet-20240620')")
        print("  - 智谱AI GLM-4.6: ChatZhipuAI(model='glm-4') (需要 langchain-community)")
        print("  - 通义千问: ChatTongyi(model='qwen-plus') (需要 langchain-community)")
        print("\n只需在创建 RefereeAgentSDK 时传入不同的 LLM 实例即可。")

        # 演示 Player Agent
        print("\n" + "-"*60)
        print("Player Agent 示例")
        print("-"*60)
        base_player = BasePlayerAgent("playerA")
        player_sdk = PlayerAgentSDK(base_player, llm, strategy="aggressive")

        observation = {
            "hand_size": 0,
            "prizes": 6,
            "deck_size": 53,
        }

        decision = player_sdk.invoke(observation)
        print(f"✓ Player Agent 决策: {decision}")

    except Exception as e:
        print(f"\n✗ 使用 LangChain Agents 时出错: {e}")
        print("\n可能的原因：")
        print("  - 缺少或无效的 API key")
        print("  - API 配额已用完")
        print("  - 网络连接问题")
        print("\n基础 RefereeAgent（不使用 SDK）仍可使用。")


if __name__ == "__main__":
    main()
