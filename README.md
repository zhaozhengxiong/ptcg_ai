# PTCG AI 原型

本仓库实现了一个用于宝可梦集换式卡牌游戏（PTCG）的 AI 对战与 AI 裁判原型系统，对应的业务背景详见 `doc/requirement.md`。项目聚焦于三类智能体的协作：**规则裁判 Referee Agent**、**玩家 Player Agent** 以及只接受裁判调用的 **Game Tools 原子操作集**，并提供可落地的持久化接口、牌库解析工具和轻量级规则知识库。

## 目前具备的能力

- **严谨的状态建模**：`CardDefinition / CardInstance / GameState` 等数据模型覆盖卡牌、区域（牌库、手牌、奖赏区、Lost Zone 等）与整体对局快照，可直接用于审计与回放。
- **原子化工具集**：`GameTools` 暴露抽卡、洗牌、奖赏卡结算、随机弃牌、跨区域移动、日志记录等底层操作，所有操作自动写入结构化 `GameLogEntry`。
- **AI 裁判管控流程**：`RefereeAgent` 校验玩家请求、维护回合状态，并在必要时引用 `RuleKnowledgeBase` 返回匹配条款。
- **数据持久化**：`DatabaseClient` 在检测到 `psycopg` 不可用时退化到 `InMemoryDatabase`，方便本地开发，同时兼容 PostgreSQL（表结构参考 `data_back_up/ptcg_backup.sql`）。
- **牌库与规则素材**：`CardLibrary` 可从 `doc/cards/en/*.json` 导入官方卡牌数据；`RuleKnowledgeBase` 支持 JSON 或纯文本，便于从规则 PDF 的离线解析结果中构建检索式知识库。
- **玩家基类与模拟工具**：`PlayerAgent` 自带记忆缓冲，`simulation.py` 提供构建套牌、加载规则文本、跑一轮回合的示例化能力。

## 仓库结构

```
src/ptcg_ai/         # 核心源码
tests/               # pytest 测试
doc/                 # 需求文档、规则 PDF、官方卡牌 JSON 数据
data_back_up/        # PostgreSQL 示例备份（schema & 初始数据）
extract_rulebook.py  # 规则书 PDF 提取脚本
```

### 核心模块速览

| 模块 | 说明 |
| ---- | ---- |
| `models.py` | 定义卡牌、区域、玩家、整局状态及日志的数据结构，并提供快照导出能力。 |
| `game_tools.py` | 封装裁判可调用的原子操作。所有状态变更都会写入数据库日志，并支持可重放的随机种子。 |
| `referee.py` | 实现 Referee Agent，对玩家请求进行合法性校验、驱动 Game Tools、维护回合/阶段。 |
| `player.py` | 玩家 AI 基类，内置简单决策策略与记忆体；可作为强化学习或检索式策略的母板。 |
| `card_loader.py` | 读取官方卡牌 JSON，实例化 60 张唯一 UID 的对战套牌。 |
| `rulebook.py` | 规则知识库封装，支持文本解析、JSON 导入与模糊检索。 |
| `simulation.py` | 快速接线工具：构建套牌、加载规则文本、驱动 `run_turn` 以串联裁判与玩家代理。 |
| `database.py` | `DatabaseClient` 对 PostgreSQL 进行了包裹，并提供 `InMemoryDatabase` 以便离线开发测试。 |

## 数据与文档资源

- `doc/requirement.md`：产品/系统需求全貌（架构、角色、工具原语、安全约束、流程示例）。
- `doc/par_rulebook_en.pdf`：官方规则 PDF（需先转成文本再喂给 `RuleKnowledgeBase`）。
- `doc/rulebook_extracted.txt`：从 PDF 提取的规则文本（可通过 `extract_rulebook.py` 生成）。
- `doc/cards/en/*.json`：多版本官方卡牌数据，可按需挑选集合。
- `data_back_up/ptcg_backup.sql`：PostgreSQL schema 及部分示例数据，方便搭建真实的日志/对局存储。

## 快速开始

### 1. 准备环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip pytest "psycopg[binary]"
pip install -e .
```

> 若只做内存级开发，可不安装 psycopg，`DatabaseClient` 会自动回退到 `InMemoryDatabase`。

### 2. 提取规则书文本（首次运行需要）

如果 `doc/rulebook_extracted.txt` 不存在，需要先从 PDF 提取规则文本：

```bash
# 安装 PyMuPDF（用于 PDF 文本提取）
pip install PyMuPDF

# 运行提取脚本
python extract_rulebook.py
```

脚本会从 `doc/par_rulebook_en.pdf` 提取文本并保存到 `doc/rulebook_extracted.txt`，同时显示提取进度和统计信息。

### 3. 运行测试

```bash
pytest
```

当前用例集中验证了 60 张唯一 UID 的套牌合法性。可据此扩展更多规则与流程验证。

### 4. 最小示例

```python
from pathlib import Path
from ptcg_ai.simulation import build_deck, load_rulebook_text, run_turn
from ptcg_ai.player import PlayerAgent
from ptcg_ai.referee import RefereeAgent

rulebook = load_rulebook_text(Path("doc/rulebook_extracted.txt"))

deck_a = build_deck("playerA", Path("doc/deck/deck1.txt"))
deck_b = build_deck("playerB", Path("doc/deck/deck1.txt"))

referee = RefereeAgent.create(
    match_id="demo-001",
    player_decks={"playerA": deck_a, "playerB": deck_b},
    knowledge_base=rulebook,
)

players = {"playerA": PlayerAgent("playerA"), "playerB": PlayerAgent("playerB")}
run_turn(referee, players)
```

该流程演示了如何：
1. 载入卡牌与规则；
2. 组建 60 张唯一 UID 的套牌；
3. 由裁判完成初始化、洗牌、发奖赏卡；
4. 调用 `run_turn` 让玩家代理提交操作，并通过裁判完成验证与日志记录。

## 工具脚本

### 规则书提取脚本

`extract_rulebook.py` 用于从 PDF 规则书提取文本：

- **功能**：使用 PyMuPDF 从 `doc/par_rulebook_en.pdf` 提取文本
- **输出**：生成 `doc/rulebook_extracted.txt` 供 `RuleKnowledgeBase` 使用
- **特性**：
  - 自动清理多余空白行
  - 显示提取进度和统计信息
  - 检测符合规则格式的条目（以数字编号开头的行）
  - 提供详细的错误提示

**使用方法**：
```bash
pip install PyMuPDF
python extract_rulebook.py
```

## 开发建议与下一步

1. **扩充 Game Tools**：根据 `doc/requirement.md` 中的原语清单，继续为状态异常、特殊规则、附件结算等场景添加底层操作。
2. **丰富 PlayerAgent 策略**：可接入强化学习、蒙特卡洛搜索或检索式提示，结合 `PlayerMemory` 形成连贯决策。
3. **落地 PostgreSQL**：利用 `data_back_up/ptcg_backup.sql` 恢复数据库，完善 `match_logs`、`matches` 等表的 schema，并将 `DatabaseClient` 切换到真实实例。
4. **规则知识库增强**：改进 `extract_rulebook.py` 以支持更精准的章节识别和结构化提取，或集成向量检索以提升规则匹配精度。

## 相关文档

- 业务需求：`doc/requirement.md`
- 规则书（英文 PDF）：`doc/par_rulebook_en.pdf`
- 卡牌数据源：`doc/cards/en/*.json`
- 数据库备份：`data_back_up/ptcg_backup.sql`
