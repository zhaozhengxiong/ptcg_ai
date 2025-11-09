# PTCG AI 对战与裁判系统

本仓库实现了一个完整的宝可梦集换式卡牌游戏（PTCG）AI 对战与 AI 裁判系统，对应的业务背景详见 `doc/requirement.md`。系统采用微服务架构，支持 LangChain Agents 集成、向量搜索、记忆管理、事件流等高级功能。

## 系统架构

系统由以下核心组件构成：

- **规则裁判 Referee Agent**：基于 LangChain Agents，负责验证玩家操作、执行规则判定、调用 Game Tools，支持多模型后端（OpenAI、Anthropic、智谱AI GLM-4.6、通义千问等）
- **玩家 Player Agent**：基于 LangChain Agents，具备决策与记忆能力，支持多模型后端
- **Game Tools 服务**：gRPC 微服务，提供原子化游戏操作接口（仅可被 Referee Agent 调用）
- **State Sync 服务**：异步状态同步服务，支持乐观锁
- **Rule KB 服务**：规则知识库服务，支持向量搜索和语义检索
- **MemoryStore 服务**：智能体记忆管理，支持嵌入向量和自动压缩
- **Simulator API**：REST API 服务，提供对局管理、状态查询、回放功能
- **Admin Console**：Next.js 管理控制台，支持对局监控、人工确认、案例管理

## 目前具备的能力

### 核心功能

- **严谨的状态建模**：`CardDefinition / CardInstance / GameState` 等数据模型覆盖卡牌、区域（牌库、手牌、奖赏区、Lost Zone 等）与整体对局快照，可直接用于审计与回放
- **原子化工具集**：`GameTools` 暴露抽卡、洗牌、奖赏卡结算、随机弃牌、跨区域移动、Lost Zone 操作、异常状态管理等底层操作，所有操作自动写入结构化 `GameLogEntry`
- **AI 裁判管控流程**：`RefereeAgent` 集成 LangChain Agents，校验玩家请求、维护回合状态，并在必要时引用 `RuleKnowledgeBase` 返回匹配条款，支持多模型后端
- **向量搜索**：规则知识库支持使用 `text-embedding-3-large` 和 pgvector 进行语义检索，提升规则匹配准确性
- **智能体记忆**：MemoryStore 服务支持记忆嵌入、语义检索和自动压缩，帮助智能体学习与决策优化
- **数据持久化**：`DatabaseClient` 支持 PostgreSQL（含 pgvector 扩展）和内存回退，方便本地开发与生产部署

### 微服务架构

- **Game Tools gRPC 服务**：提供游戏操作接口，支持 mTLS 认证
- **State Sync 服务**：异步状态管理，支持乐观锁和事务处理
- **Rule KB 服务**：FastAPI 服务，提供规则查询和向量搜索
- **Simulator API**：FastAPI REST 服务，提供对局管理 API
- **Admin Console API**：管理后台 API，支持人工确认和案例管理

### 基础设施

- **容器化**：所有服务提供 Dockerfile 和 docker-compose 配置
- **CI/CD**：GitHub Actions 工作流，支持自动化测试和部署
- **可观测性**：OpenTelemetry 集成，支持 Prometheus 指标和分布式追踪
- **事件流**：Kafka 集成，支持状态变更事件发布

## 仓库结构

```
ptcg_agents/
├── agents/                    # LangChain Agents 智能体实现
│   ├── referee/               # 裁判 Agent（LangChain 集成）
│   └── players/               # 玩家 Agent（LangChain 集成）
├── services/                  # 微服务
│   ├── game_tools/            # Game Tools gRPC 服务
│   ├── state_sync/            # 状态同步服务
│   ├── rule_kb/               # 规则知识库服务（向量搜索）
│   └── memory_store/          # 记忆存储服务
├── apps/                      # 应用层
│   ├── simulator_api/         # 对局管理 REST API
│   └── admin_console/         # 管理控制台（Next.js + API）
├── src/ptcg_ai/               # 核心业务逻辑
│   ├── models.py              # 数据模型
│   ├── game_tools.py          # 游戏工具原语
│   ├── referee.py             # 裁判 Agent 基础实现
│   ├── player.py              # 玩家 Agent 基础实现
│   ├── rulebook.py            # 规则知识库
│   ├── database.py            # 数据库客户端
│   ├── card_loader.py         # 卡牌加载器
│   ├── card_effects.py        # 卡牌效果执行
│   └── simulation.py          # 模拟工具
├── db/migrations/             # 数据库迁移脚本
├── infra/                     # 基础设施
│   ├── docker/                # Docker 配置
│   ├── k8s/                   # Kubernetes 配置
│   ├── terraform/             # Terraform 配置
│   └── certs/                 # mTLS 证书生成
├── tests/                     # 测试
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── e2e/                   # 端到端测试
├── .github/workflows/         # CI/CD 工作流
├── doc/                       # 文档和资源
└── data_back_up/              # 数据库备份
```

### 核心模块速览

| 模块 | 说明 |
| ---- | ---- |
| `models.py` | 定义卡牌、区域、玩家、整局状态及日志的数据结构，并提供快照导出能力 |
| `game_tools.py` | 封装裁判可调用的原子操作。所有状态变更都会写入数据库日志，并支持可重放的随机种子 |
| `referee.py` | 实现 Referee Agent 基础类，对玩家请求进行合法性校验、驱动 Game Tools、维护回合/阶段 |
| `player.py` | 玩家 AI 基类，内置简单决策策略与记忆体 |
| `rulebook.py` | 规则知识库封装，支持文本解析、JSON 导入与模糊检索 |
| `agents/referee/agent.py` | Referee Agent 的 LangChain 集成 |
| `agents/referee/tools.py` | Referee Agent 的 LangChain 工具定义 |
| `agents/players/base_agent.py` | Player Agent 的 LangChain 集成 |
| `agents/players/tools.py` | Player Agent 的 LangChain 工具定义 |
| `services/rule_kb/vector_search.py` | 规则向量搜索实现 |
| `services/memory_store/service.py` | 记忆存储和检索服务 |

## 数据与文档资源

- `doc/requirement.md`：产品/系统需求全貌（架构、角色、工具原语、安全约束、流程示例）
- `doc/par_rulebook_en.pdf`：官方规则 PDF（需先转成文本再喂给 `RuleKnowledgeBase`）
- `doc/rulebook_extracted.txt`：从 PDF 提取的规则文本（可通过 `extract_rulebook.py` 生成）
- `doc/cards/en/*.json`：多版本官方卡牌数据，可按需挑选集合
- `data_back_up/ptcg_backup.sql`：PostgreSQL schema 及部分示例数据，方便搭建真实的日志/对局存储

## 快速开始

### 1. 准备环境

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
```

### 2. 数据库设置

#### 使用 PostgreSQL（推荐）

```bash
# 安装 PostgreSQL 和 pgvector 扩展
# 创建数据库
createdb ptcg

# 运行迁移脚本
psql -d ptcg -f db/migrations/000_create_base_tables.sql
psql -d ptcg -f db/migrations/001_add_memory_embeddings.sql

# 或使用备份恢复
psql -d ptcg < data_back_up/ptcg_backup.sql
```

#### 使用 Docker Compose（最简单）

```bash
cd infra/docker
docker-compose up -d
```

这将启动 PostgreSQL（含 pgvector）、Game Tools 服务、Simulator API 和 Rule KB 服务。

### 3. 提取规则书文本（首次运行需要）

如果 `doc/rulebook_extracted.txt` 不存在，需要先从 PDF 提取规则文本：

```bash
# 安装 PyMuPDF（用于 PDF 文本提取）
pip install PyMuPDF

# 运行提取脚本
python extract_rulebook.py
```

### 4. 生成 mTLS 证书（可选，用于服务间认证）

```bash
cd infra/certs
./generate_certs.sh
```

### 5. 运行测试

```bash
pytest
```

### 6. 启动服务

#### 一键启动所有服务（推荐）

```bash
# 启动所有服务（Game Tools、Simulator API、Rule KB）
./start_services.sh

# 停止所有服务
./stop_services.sh
```

脚本会自动：
- 检查并激活虚拟环境
- 在后台启动所有服务
- 保存 PID 文件到 `.pids/` 目录
- 将日志输出到 `logs/` 目录
- 检查服务是否已在运行，避免重复启动

启动后，服务将在以下端口运行：
- **Game Tools gRPC**: `localhost:50051`
- **Simulator API**: `http://localhost:8000`
- **Rule KB API**: `http://localhost:8001`

#### 单独启动服务

如果需要单独启动某个服务：

**启动 Game Tools gRPC 服务**

```bash
python -m services.game_tools
```

**启动 Simulator API**

```bash
# 方式 1: 使用启动脚本
./apps/simulator_api/run.sh

# 方式 2: 从项目根目录运行（需要激活虚拟环境）
source .venv/bin/activate
python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000

# 方式 3: 使用 Python 模块
source .venv/bin/activate
python -m apps.simulator_api
```

**启动 Rule KB 服务**

```bash
# 从项目根目录运行（需要激活虚拟环境）
source .venv/bin/activate
python -m uvicorn services.rule_kb.service:app --host 0.0.0.0 --port 8001
```

### 7. 使用示例

#### 基础使用（不使用 SDK）

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

#### 使用 LangChain Agents

```python
from agents.referee import RefereeAgentSDK
from agents.players import PlayerAgentSDK
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatZhipuAI  # GLM-4.6
from src.ptcg_ai.referee import RefereeAgent as BaseRefereeAgent
from src.ptcg_ai.player import PlayerAgent as BasePlayerAgent

# 创建基础 Referee Agent
base_referee = BaseRefereeAgent.create(...)

# 选择模型（支持 OpenAI、Anthropic、智谱AI GLM-4.6、通义千问等）
llm = ChatOpenAI(model="gpt-4o")  # OpenAI
# llm = ChatAnthropic(model="claude-3-5-sonnet-20240620")  # Anthropic
# llm = ChatZhipuAI(model="glm-4")  # 智谱AI GLM-4.6 (需要设置 ZHIPU_API_KEY)

# 创建 LangChain Agent
referee_sdk = RefereeAgentSDK(base_referee, llm)

# 使用 LangChain 原生接口处理玩家请求
result = referee_sdk.invoke({
    "input": {
        "player_id": "playerA",
        "action": "draw",
        "payload": {"count": 1}
    },
    "chat_history": []
})

# Player Agent 示例
base_player = BasePlayerAgent("playerA")
player_sdk = PlayerAgentSDK(base_player, llm, strategy="aggressive")

observation = {"hand_size": 0, "prizes": 6}
decision = player_sdk.invoke(observation)
```

#### 使用向量搜索

```python
from services.rule_kb.vector_search import VectorRuleSearch
from services.state_sync import create_pool
import asyncio

async def main():
    pool = await create_pool("postgresql://user:pass@localhost/ptcg")
    vector_search = VectorRuleSearch(pool=pool)
    
    # 索引规则
    await vector_search.index_rules(rulebook)
    
    # 搜索规则
    results = await vector_search.search("energy attachment", limit=5)
    for entry in results:
        print(f"{entry.section}: {entry.text}")

asyncio.run(main())
```

## API 文档

### Simulator API

启动服务后，访问 `http://localhost:8000/docs` 查看 Swagger 文档。

主要端点：
- `POST /matches` - 创建新对局
- `GET /matches/{match_id}` - 获取对局状态
- `GET /matches/{match_id}/logs` - 获取对局日志
- `POST /matches/{match_id}/replay` - 回放对局

### Rule KB API

访问 `http://localhost:8001/docs` 查看 API 文档。

主要端点：
- `POST /query` - 查询规则（支持向量搜索）

## 开发指南

### 添加新的 Game Tools 原语

1. 在 `src/ptcg_ai/game_tools.py` 中添加方法
2. 在 `services/game_tools/proto/game_tools.proto` 中添加 gRPC 定义
3. 在 `services/game_tools/service.py` 中实现 gRPC 处理
4. 运行 `python -m grpc_tools.protoc` 重新生成 proto 代码

### 添加新的智能体策略

在 `agents/players/strategies/` 中创建新的策略类，继承 `PlayerAgentSDK`。

### 数据库迁移

创建新的迁移文件：

```bash
# 创建迁移文件
touch db/migrations/002_your_migration.sql

# 运行迁移
psql -d ptcg -f db/migrations/002_your_migration.sql
```

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

### mTLS 证书生成

`infra/certs/generate_certs.sh` 用于生成服务间认证证书：

```bash
cd infra/certs
./generate_certs.sh
```

## 部署

### Docker Compose 部署

```bash
cd infra/docker
docker-compose up -d
```

### Kubernetes 部署

```bash
kubectl apply -f infra/k8s/
```

### Terraform 部署（云基础设施）

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

## CI/CD

项目使用 GitHub Actions 进行持续集成：

- **Lint**：使用 ruff 和 mypy 进行代码检查
- **Test**：运行单元测试、集成测试和 E2E 测试
- **Build**：构建 Docker 镜像

工作流文件：`.github/workflows/ci.yml`

## 监控与可观测性

- **Prometheus**：指标收集（端口 9090）
- **OpenTelemetry**：分布式追踪
- **Grafana**：可视化仪表板（需自行配置）

## 安全

- **mTLS**：服务间通信使用双向 TLS 认证
- **OAuth2**：用户 API 使用 OAuth2 认证
- **令牌验证**：Game Tools 服务验证 Referee Agent 令牌

## 开发建议与下一步

1. **完善卡牌效果**：扩展 `card_effects.py` 以支持更多卡牌效果
2. **增强 AI 策略**：实现更复杂的玩家决策策略
3. **优化向量搜索**：调整相似度阈值和索引参数
4. **完善 Admin Console**：实现完整的管理界面
5. **性能优化**：优化数据库查询和向量搜索性能
6. **扩展测试**：增加更多集成测试和 E2E 测试用例

## 相关文档

- 业务需求：`doc/requirement.md`
- 规则书（英文 PDF）：`doc/par_rulebook_en.pdf`
- 卡牌数据源：`doc/cards/en/*.json`
- 数据库备份：`data_back_up/ptcg_backup.sql`

## 许可证

[根据项目实际情况添加许可证信息]
