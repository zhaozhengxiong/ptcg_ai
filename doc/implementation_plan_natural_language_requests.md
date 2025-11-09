# 自然语言请求实施计划

## 一、需求变更概述

**变更内容**：将 Player Agent 向规则 Agent 提出请求的方式从结构化指令（JSON/OperationRequest）改为自然语言。

**变更原因**：
- 更符合人类玩家的交互方式
- 提高系统的灵活性和可扩展性
- 规则 Agent 可以更好地理解玩家意图并进行自然语言对话

**影响范围**：
- Player Agent 的请求生成逻辑
- Referee Agent 的请求解析与处理逻辑
- 主游戏循环的请求传递机制
- 错误处理和反馈机制

---

## 二、当前架构分析

### 2.1 当前实现流程

```
Player Agent (LangChain Agent)
  ↓ 使用 decide_action 工具
  ↓ 生成 OperationRequest {action, payload}
  ↓
Referee Agent.handle_request(OperationRequest)
  ↓ 解析 action 和 payload
  ↓ 调用对应的 handler 方法
  ↓
Game Tools (执行实际操作)
```

### 2.2 关键代码位置

1. **Player Agent 请求生成**：
   - `agents/players/base_agent.py`: `PlayerAgentSDK.invoke()` - 生成 OperationRequest
   - `agents/players/tools.py`: `decide_action` 工具 - 结构化工具调用

2. **Referee Agent 请求处理**：
   - `src/ptcg_ai/referee.py`: `RefereeAgent.handle_request()` - 接收 OperationRequest
   - `agents/referee/agent.py`: `RefereeAgentSDK.invoke()` - 已支持自然语言输入（但当前未使用）

3. **主游戏循环**：
   - `src/main.py`: `run_full_game()` - 传递 OperationRequest 到 Referee

---

## 三、实施计划

### 阶段一：需求文档更新 ✅

- [x] 修改 `requirement.md` 中 Player Agent 职责描述
- [x] 确认交互规范示例已符合自然语言要求

### 阶段二：Referee Agent 自然语言理解能力增强 ✅

#### 2.1 增强 RefereeAgentSDK 的自然语言处理能力

**目标**：让 Referee Agent 能够理解自然语言请求并转换为操作

**任务清单**：
- [x] 完善 `RefereeAgentSDK` 的指令（instructions），明确如何解析自然语言请求
- [x] 增强 `create_referee_tools` 中的工具，添加自然语言解析工具
- [x] 实现自然语言到结构化操作的转换逻辑
- [x] 添加请求验证和错误处理机制

**技术方案**：
1. 在 Referee Agent 的 system prompt 中添加自然语言解析指南
2. 创建 `parse_player_request` 工具，用于从自然语言中提取：
   - 操作类型（action）
   - 操作参数（payload，包括卡牌 UID、目标等）
3. 使用 LLM 的意图识别能力，将自然语言转换为结构化操作
4. 在转换后调用现有的 `execute_action` 工具

**示例转换**：
```
输入："我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"
↓
解析为：
{
  "action": "attach_energy",
  "payload": {
    "energy_card_id": "playerA-deck-020",
    "pokemon_id": "playerA-deck-015"
  }
}
```

#### 2.2 修改 RefereeAgent 接口 ✅

**任务清单**：
- [x] 修改 `RefereeAgent.handle_request()` 支持自然语言输入
- [x] 或创建新的 `handle_natural_language_request()` 方法
- [x] 保持向后兼容性（同时支持 OperationRequest 和自然语言）

**建议方案**：
- 在 `RefereeAgent` 中添加 `handle_natural_language_request(player_id: str, request_text: str)` 方法
- 该方法内部使用 `RefereeAgentSDK` 进行自然语言解析
- 解析后调用现有的 `handle_request()` 方法

### 阶段三：Player Agent 请求生成方式修改 ✅

#### 3.1 修改 Player Agent 生成自然语言请求

**目标**：让 Player Agent 生成自然语言请求而不是结构化 OperationRequest

**任务清单**：
- [x] 修改 `PlayerAgentSDK.invoke()` 方法，生成自然语言请求
- [x] 更新 `base_agent.py` 中的 instructions，指导 AI 生成自然语言请求
- [x] 移除或修改 `decide_action` 工具，改为生成自然语言描述
- [x] 确保自然语言请求包含必要的 UID 信息

**技术方案**：
1. 修改 Player Agent 的 system prompt，要求生成自然语言请求
2. 示例格式：
   ```
   "我想使用手牌中的Nest Ball(uid:playerA-deck-028)来搜索牌库中的基础宝可梦"
   "我想将备战区的Pikachu(uid:playerA-deck-017)切换到战斗区"
   "我想使用战斗区Charizard(uid:playerA-deck-015)的'Blaze'攻击"
   ```
3. 保留 `decide_action` 工具，但修改其输出为自然语言描述
4. 或者创建新的 `make_request` 工具，专门用于生成自然语言请求

#### 3.2 处理回合结束逻辑 ✅

**任务清单**：
- [x] 明确自然语言中如何表达"结束回合"
- [x] 处理"我想结束回合"、"我不进行攻击"等自然语言表达

### 阶段四：主游戏循环适配 ✅

#### 4.1 修改主游戏循环

**任务清单**：
- [x] 修改 `src/main.py` 中的 `run_full_game()` 函数
- [x] 将 Player Agent 返回的自然语言请求传递给 Referee Agent
- [x] 更新日志输出，显示自然语言请求
- [x] 处理错误反馈，确保错误信息能帮助 Player Agent 修正请求

**代码修改点**：
```python
# 当前代码：
request = player_agent.invoke(observation)  # 返回 OperationRequest
result = referee.handle_request(request)

# 修改后：
request_text = player_agent.invoke(observation)  # 返回自然语言字符串
result = referee.handle_natural_language_request(player_id, request_text)
```

#### 4.2 错误处理和反馈机制 ✅

**任务清单**：
- [x] 确保 Referee Agent 的错误反馈是自然语言
- [x] 将错误信息传递给 Player Agent 的观察信息
- [x] 支持多轮对话（Player 请求 → Referee 反馈 → Player 修正）

**示例错误反馈**：
```
"操作失败：你尝试使用的能量卡(uid:playerA-deck-020)不在手牌中，请检查你的手牌列表"
"操作失败：本回合已经执行过一次附能操作，每回合只能附能一次"
```

### 阶段五：测试与验证

#### 5.1 单元测试

**任务清单**：
- [ ] 测试 Referee Agent 的自然语言解析能力
- [ ] 测试各种操作类型的自然语言表达
- [ ] 测试错误处理和反馈机制
- [ ] 测试边界情况（模糊请求、缺少信息等）

#### 5.2 集成测试

**任务清单**：
- [ ] 测试完整的 Player → Referee 交互流程
- [ ] 测试多轮对话和错误修正
- [ ] 测试游戏完整对局

#### 5.3 示例测试用例

```
测试用例1：附能操作
输入："我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"
预期：成功执行 attach_energy 操作

测试用例2：使用训练家卡
输入："我想使用手牌中的Iono(uid:playerA-deck-037)"
预期：成功执行 play_trainer 操作

测试用例3：错误处理
输入："我想使用手牌中的Iono(uid:playerA-deck-999)"  # 不存在的UID
预期：返回错误信息，提示UID不存在

测试用例4：模糊请求
输入："我想使用Iono"  # 缺少UID
预期：返回错误信息，要求提供UID
```

---

## 四、技术实现细节

### 4.1 Referee Agent 自然语言解析工具

**工具设计**：
```python
def parse_player_request(request_text: str, game_state: Dict) -> Dict:
    """从自然语言请求中解析出操作类型和参数。
    
    输入示例：
    - "我想将手牌中的基础超能量(uid:playerA-deck-020)附到Arceus V(uid:playerA-deck-015)上"
    - "我想使用手牌中的Nest Ball(uid:playerA-deck-028)"
    
    输出格式：
    {
        "action": "attach_energy",
        "payload": {
            "energy_card_id": "playerA-deck-020",
            "pokemon_id": "playerA-deck-015"
        }
    }
    """
```

### 4.2 Player Agent 请求生成格式

**自然语言请求模板**：
- 附能：`"我想将手牌中的{能量卡名称}(uid:{uid})附到{宝可梦名称}(uid:{uid})上"`
- 使用训练家卡：`"我想使用手牌中的{训练家卡名称}(uid:{uid})"`
- 放置宝可梦：`"我想将手牌中的{宝可梦名称}(uid:{uid})放置到备战区"`
- 进化：`"我想将{基础宝可梦}(uid:{uid})进化为{进化宝可梦}(uid:{uid})"`
- 撤退：`"我想将战斗区的{宝可梦名称}(uid:{uid})撤退，切换到备战区的{宝可梦名称}(uid:{uid})"`
- 使用能力：`"我想使用{宝可梦名称}(uid:{uid})的{能力名称}能力"`
- 攻击：`"我想使用{宝可梦名称}(uid:{uid})的{攻击名称}攻击{目标宝可梦}(uid:{uid})"`

### 4.3 错误处理策略

1. **UID 验证**：在解析时验证 UID 是否存在于游戏状态中
2. **参数完整性检查**：确保自然语言请求包含所有必需参数
3. **模糊请求处理**：如果请求不明确，返回澄清问题
4. **多轮对话支持**：支持 Referee 提问，Player 回答的模式

---

## 五、实施时间线

### 第一周：Referee Agent 增强
- Day 1-2: 完善 RefereeAgentSDK 的自然语言处理能力
- Day 3-4: 实现自然语言解析工具
- Day 5: 单元测试和调试

### 第二周：Player Agent 修改
- Day 1-2: 修改 Player Agent 生成自然语言请求
- Day 3-4: 更新 instructions 和工具定义
- Day 5: 单元测试和调试

### 第三周：集成和测试
- Day 1-2: 修改主游戏循环
- Day 3-4: 集成测试和错误处理
- Day 5: 完整对局测试和优化

---

## 六、风险评估与应对

### 6.1 风险点

1. **自然语言解析准确性**
   - 风险：LLM 可能无法准确解析所有自然语言变体
   - 应对：提供清晰的请求格式指南，使用结构化提示词

2. **UID 提取错误**
   - 风险：从自然语言中提取 UID 可能出错
   - 应对：使用正则表达式辅助提取，添加验证步骤

3. **向后兼容性**
   - 风险：修改可能影响现有功能
   - 应对：保持 OperationRequest 接口，新增自然语言接口

4. **性能影响**
   - 风险：自然语言解析可能增加延迟
   - 应对：优化提示词，使用更快的模型或缓存解析结果

### 6.2 回退方案

如果自然语言方案遇到重大问题，可以：
1. 保留 OperationRequest 作为备选方案
2. 实现混合模式：优先自然语言，失败时回退到结构化请求
3. 提供配置开关，允许选择请求方式

---

## 七、后续优化方向

1. **多轮对话支持**：支持 Referee 提问澄清，Player 回答
2. **请求模板学习**：从历史对局中学习常见的自然语言表达
3. **意图识别优化**：使用专门的意图识别模型提高准确性
4. **多语言支持**：支持英文、日文等自然语言请求

---

## 八、验收标准

1. ✅ Player Agent 能够生成包含 UID 的自然语言请求
2. ✅ Referee Agent 能够准确解析自然语言请求并执行操作
3. ✅ 错误处理机制能够提供清晰的反馈
4. ✅ 完整对局能够正常运行
5. ✅ 所有测试用例通过

---

## 九、相关文件清单

需要修改的文件：
- `doc/requirement.md` ✅ (已完成)
- `agents/referee/agent.py` (需要增强)
- `agents/referee/tools.py` (需要添加解析工具)
- `agents/players/base_agent.py` (需要修改请求生成)
- `agents/players/tools.py` (可能需要修改工具定义)
- `src/ptcg_ai/referee.py` (可能需要添加自然语言接口)
- `src/main.py` (需要修改主循环)

需要新增的文件：
- `agents/referee/natural_language_parser.py` (可选，如果解析逻辑复杂)

