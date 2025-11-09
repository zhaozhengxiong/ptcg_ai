# Pattern Matcher 优化分析报告

## 执行摘要

基于对 `advanced-manual-split` 文件夹下所有文件的系统性阅读和对 `pattern_matcher.py` 代码的深入分析，本文档识别了多个优化点和缺失的模式。

## 一、缺失的模式识别

### 1.1 Effects (C系列) 缺失模式

#### C-06 Heal damage (治疗伤害)
- **规则描述**: "Heal ●● damage" - 治疗指定数量的伤害
- **当前状态**: ❌ 未实现
- **优先级**: 高
- **示例**: 
  - "Heal all damage from 1 of your Pokémon"
  - "Heal 20 damage from this Pokémon"
- **建议实现**:
```python
HEAL_DAMAGE = re.compile(
    r"heal (?:all |(\d+) )?damage (?:from|on) (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

#### C-08 Move damage counters (移动伤害计数器)
- **规则描述**: "Move ▲ number of damage counters from ●● to ■■"
- **当前状态**: ❌ 未实现
- **优先级**: 高
- **示例**:
  - "Move 1 damage counter from 1 Pokémon to another Pokémon"
  - "Move all damage counters from this Pokémon to your opponent's Active Pokémon"
- **建议实现**:
```python
MOVE_DAMAGE_COUNTERS = re.compile(
    r"move (?:all|(\d+)) damage counters? from (.+?) to (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

#### C-10 Move Energy (移动能量)
- **规则描述**: "Move ▲ amount of ● Energy to ■■"
- **当前状态**: ❌ 未实现
- **优先级**: 高
- **示例**:
  - "Move an Energy from this Pokémon to 1 of your Benched Pokémon"
  - "Move a [P] Energy from 1 of your Pokémon to another of your Pokémon"
- **建议实现**:
```python
MOVE_ENERGY = re.compile(
    r"move (?:an|a|(\d+)) (?:amount of )?(.+? )?energy (?:from|attached to) (.+?) to (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

#### C-13 Devolve (退化)
- **规则描述**: "Devolve a Pokémon by removing an Evolution card from it"
- **当前状态**: ❌ 未实现
- **优先级**: 中
- **示例**:
  - "If your opponent's Active Pokémon is an evolved Pokémon, devolve it by putting the highest Stage Evolution card on it into your opponent's hand"
- **建议实现**:
```python
DEVOLVE = re.compile(
    r"devolve (.+?) by (?:removing|putting) (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

### 1.2 Damage Calculation (B系列) 缺失模式

#### B-08 Damage to multiple Pokémon (对多个宝可梦造成伤害)
- **规则描述**: "This attack does ▲▲ damage (each) to ● of your opponent's Pokémon"
- **当前状态**: ❌ 未实现
- **优先级**: 中
- **示例**:
  - "This attack does 20 damage to 1 of your opponent's Pokémon"
  - "This attack does 50 damage to 2 of your opponent's Pokémon"
- **建议实现**:
```python
DAMAGE_TO_MULTIPLE = re.compile(
    r"does (\d+) damage (?:\(each\) )?to (\d+) of your opponent'?s pokémon",
    re.IGNORECASE
)
```

#### B-09 Damage to self (对自己造成伤害)
- **规则描述**: "This Pokémon does ● damage to itself"
- **当前状态**: ❌ 未实现
- **优先级**: 中
- **示例**:
  - "This Pokémon does 20 damage to itself"
- **建议实现**:
```python
DAMAGE_TO_SELF = re.compile(
    r"this pokémon does (\d+) damage to itself",
    re.IGNORECASE
)
```

### 1.3 Glossary (D系列) 缺失模式

#### D-01 "The attack does nothing" (攻击无效)
- **规则描述**: 攻击失败或无效
- **当前状态**: ❌ 未实现
- **优先级**: 中
- **示例**:
  - "Flip a coin. If tails, this attack does nothing"
- **建议实现**:
```python
ATTACK_DOES_NOTHING = re.compile(
    r"(?:this attack|that attack) does nothing",
    re.IGNORECASE
)
```

#### D-02 "As many as you like" / "any amount" (任意数量)
- **规则描述**: 选择任意数量的指定卡牌
- **当前状态**: ⚠️ 部分支持（在搜索中支持 "up to"，但缺少 "any amount"）
- **优先级**: 中
- **示例**:
  - "Discard any amount of [R] Energy from your Pokémon"
  - "Reveal any number of Moomoo Milk cards in your hand"
- **建议改进**: 在 `_parse_search_criteria` 中添加对 "any amount" 和 "any number" 的支持

#### D-03 "All" (全部)
- **规则描述**: 选择所有指定的卡牌
- **当前状态**: ❌ 未实现
- **优先级**: 中
- **示例**:
  - "Discard all Special Energy from each Pokémon"
  - "Shuffle all of their hand into their deck"
- **建议实现**:
```python
ALL_PATTERN = re.compile(
    r"(?:discard|shuffle|move|attach) all (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

### 1.4 Other text (E系列) 缺失模式

#### E-09 "Before doing damage" (在造成伤害之前)
- **规则描述**: 在伤害计算之前执行的效果
- **当前状态**: ❌ 未实现
- **优先级**: 高
- **示例**:
  - "Before doing damage, you may discard any number of Pokémon Tool cards from your Pokémon"
- **建议实现**: 在 `parse_action_sequence` 中识别并标记 "before doing damage" 的效果

#### E-19 "Do ●●. If you do, do ▲▲." (条件链)
- **规则描述**: 条件执行链
- **当前状态**: ✅ 已实现（但可能需要改进）
- **优先级**: 低
- **建议**: 当前实现基本正确，但可以改进对复杂条件链的处理

## 二、模式准确性改进

### 2.1 Discard 模式改进

**当前问题**:
- 只支持从手牌丢弃固定数量
- 不支持从其他来源丢弃（如从宝可梦上丢弃能量）

**建议改进**:
```python
# 扩展 DISCARD_AND 模式
DISCARD_FROM = re.compile(
    r"discard (?:all|(\d+)|any amount of) (.+?) (?:from|attached to) (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

### 2.2 Energy Attachment 模式改进

**当前问题**:
- `parse_attach_action` 只检查是否允许多个目标
- 缺少对能量来源的识别（手牌、弃牌区、牌库）

**建议改进**:
```python
ATTACH_ENERGY_FROM = re.compile(
    r"attach (?:up to )?(\d+)? (.+?) energy cards? (?:from (.+?))? to (.+?)(?:\.|$)",
    re.IGNORECASE
)
```

### 2.3 Switch 模式改进

**当前问题**:
- `SWITCH_OPPONENT` 和 `SWITCH_YOUR` 模式可能不够全面
- 缺少对 "your opponent switches" 变体的支持

**建议改进**:
```python
SWITCH_OPPONENT_ACTIVE = re.compile(
    r"your opponent switches? (?:their )?active pokémon with (\d+) of (?:their )?benched pokémon",
    re.IGNORECASE
)
```

## 三、边界情况处理

### 3.1 "up to" vs "any amount" vs "as many as you like"

**规则差异**:
- **"up to X"**: 可以选择 0 到 X 之间的任意数量（除了抽牌，抽牌可以选择 0）
- **"any amount"**: 可以选择 0 或更多
- **"as many as you like"**: 可以选择任意数量（包括 0）

**当前实现**: 只支持 "up to"，需要添加对其他两种的支持

### 3.2 复杂条件链

**问题**: 当前 "if you do" 处理可能无法正确处理嵌套条件

**建议**: 使用递归或更复杂的解析器来处理嵌套条件

## 四、代码质量优化

### 4.1 代码重复

**问题**: `_parse_single_action` 方法过长（200+ 行），包含大量 if-elif 链

**建议**: 
- 将不同类型的操作解析拆分为独立方法
- 使用策略模式或注册表模式

### 4.2 正则表达式优化

**问题**: 某些正则表达式可能过于宽泛或过于严格

**建议**:
- 添加单元测试覆盖各种边界情况
- 优化正则表达式的性能

### 4.3 错误处理

**问题**: 缺少对无效输入的错误处理

**建议**:
- 添加输入验证
- 提供更详细的错误信息

## 五、性能优化

### 5.1 正则表达式编译

**当前状态**: ✅ 所有正则表达式都在类级别编译，这是好的

### 5.2 方法调用优化

**建议**: 考虑缓存某些解析结果（如果输入相同）

## 六、优先级排序

### 高优先级（必须实现）
1. C-06 Heal damage
2. C-08 Move damage counters
3. C-10 Move Energy
4. E-09 Before doing damage

### 中优先级（应该实现）
1. C-13 Devolve
2. B-08 Damage to multiple Pokémon
3. B-09 Damage to self
4. D-01 "The attack does nothing"
5. D-02 "As many as you like" / "any amount"
6. D-03 "All"
7. Discard 模式改进
8. Energy Attachment 模式改进

### 低优先级（可以考虑）
1. Switch 模式改进
2. 代码重构（拆分方法）
3. 复杂条件链处理改进

## 七、实现建议

### 7.1 分阶段实现

**阶段 1**: 实现高优先级缺失模式
**阶段 2**: 实现中优先级缺失模式和模式改进
**阶段 3**: 代码重构和性能优化

### 7.2 测试策略

- 为每个新添加的模式创建单元测试
- 使用实际卡牌文本作为测试用例
- 测试边界情况和异常输入

### 7.3 文档更新

- 更新代码注释
- 添加模式匹配的示例
- 记录已知限制和边界情况

## 八、总结

`pattern_matcher.py` 已经实现了大部分基础模式，但在 Effects (C系列) 和 Damage Calculation (B系列) 方面还有重要缺失。建议优先实现高优先级的缺失模式，然后逐步改进现有模式的准确性和代码质量。

