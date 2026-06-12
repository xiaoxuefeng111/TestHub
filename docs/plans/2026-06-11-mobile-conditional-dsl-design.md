# Mobile Conditional DSL 设计方案

**目标**：为移动端 AI 自动化增加“通用 UI 条件句框架”，让用户自然语言中的 if/else、字段为空/非空、文字出现/未出现等条件语义先被结构化，再经过安全校验后执行，避免把条件句压平成危险的线性步骤。

## 现状结论
- 当前 `apps/ui_automation/mobile_agent.py` 仍以“自然语言 → 扁平动作 JSON”为主。
- 当前 `apps/app_automation/runners/ui_flow_runner.py` 的 `input` 动作默认依赖当前焦点，虽然已兼容 `value/text` 并补了缺参报错，但仍缺少通用的目标绑定、清空、条件求值能力。
- `apps/ui_automation/ai_base.py` 已具备较好的步骤抽取、字面值保留和轻量重组能力，可复用为移动端条件框架的前置层。

## 方案选择
### 方案 A：纯规则条件框架
- 优点：可控、易解释。
- 缺点：口语化和省略表达覆盖弱，规则会快速膨胀。

### 方案 B：混合式条件框架（采用）
- 规则负责识别高风险条件句和关键字面值。
- LLM 负责把自然语言归一化为受限 DSL。
- 校验器负责关键值、关键动作、分支完整性和安全闸门。
- 执行层仅补最小运行时条件求值、聚焦、清空与中止能力。

### 方案 C：全 LLM 条件执行
- 优点：表达最强。
- 缺点：可控性最差，不适合当前“保守安全”策略。

## 架构与数据流
```text
用户自然语言
  ↓
ai_base.py 步骤抽取/字面值保留
  ↓
mobile_semantic_parser.py 生成条件 DSL
  ↓
mobile_plan_validator.py 校验 DSL 安全性
  ↓
mobile_agent.py 下放为可执行计划
  ↓
mobile_condition_evaluator.py 运行时条件求值
  ↓
ui_flow_runner.py 执行
```

## 模块划分
### 1. 步骤抽取层（复用）
- 文件：`apps/ui_automation/ai_base.py`
- 职责：提取编号步骤、保留字面值、拆解一条语句中的多个动作。

### 2. 语义解析层（新增）
- 文件：`apps/ui_automation/mobile_semantic_parser.py`
- 职责：识别普通 UI 动作、条件语义、输入目标和值，生成受限 DSL。

### 3. 安全校验层（新增）
- 文件：`apps/ui_automation/mobile_plan_validator.py`
- 职责：校验关键字面值、关键动作、条件分支完整性以及输入动作完整性。

### 4. 条件求值层（新增）
- 文件：`apps/ui_automation/mobile_condition_evaluator.py`
- 职责：根据当前界面状态对条件返回 `TRUE/FALSE/UNKNOWN`。

### 5. 执行映射层（扩展）
- 文件：`apps/ui_automation/mobile_agent.py`
- 职责：把 DSL 转为 `UiFlowRunner` 可执行动作；遇到 `UNKNOWN` 时安全中止。

### 6. 执行层（扩展）
- 文件：`apps/app_automation/runners/ui_flow_runner.py`
- 职责：补 `focus_field`、`clear_first`、条件节点执行入口、分支日志。

## DSL 设计
```json
{
  "version": "1.0",
  "mode": "safe",
  "steps": [
    {"type": "tap_text", "target": "交易"},
    {"type": "tap_text", "target": "买入"},
    {
      "type": "conditional",
      "condition": {"kind": "field_empty", "target": "资金账号"},
      "if_true": [
        {"type": "focus_field", "target": "资金账号"},
        {"type": "input", "target": "资金账号", "value": "100000120", "clear_first": true}
      ],
      "if_false": [
        {"type": "focus_field", "target": "密码"}
      ]
    },
    {"type": "focus_field", "target": "密码"},
    {"type": "input", "target": "密码", "value": "111111", "clear_first": true},
    {"type": "tap_text", "target": "交易登录"}
  ]
}
```

## 第一版支持的条件类型
- `field_empty`
- `field_not_empty`
- `text_visible`
- `text_not_visible`
- `dialog_visible`
- `status_text`

第一版暂不直接执行：
- 多层嵌套条件
- 多条件 and/or
- 无限循环 until/while
- 弱指代（如“它”“那个地方”）
- 低置信度字段状态判断

## 自动分析策略
### 规则预分析
- 识别 if/else、没有…就…、有的话…、否则…、出现…时…、为空/非空、成功/失败等高风险条件结构。
- 标记用户原文中的关键字面值、关键按钮、关键输入目标。

### LLM 语义归一化
- 仅允许输出受限 DSL。
- 强制保留关键字面值和关键动作。
- 不确定时必须输出 `unsafe_reason`，而不是猜测执行。

### 安全校验
- 输入动作必须带 `target` 与 `value`。
- 用户原文中的关键值和关键动作不可丢失。
- 条件句不可被静默压平成单一路径。
- 不能安全求值的条件必须中止，不得降级回旧的盲跑流程。

## 执行策略
### 可以直接自动执行
- `text_visible`
- `text_not_visible`
- `dialog_visible`
- `status_text`

### 只在高置信度下执行
- `field_empty`
- `field_not_empty`

### 无法判断时
- 返回 `UNKNOWN`
- 停止执行
- 记录原因和触发条件

## 验证与回退
- 单元测试：解析器、校验器、条件求值器。
- 集成测试：DSL → 可执行计划 → `UiFlowRunner` 的映射。
- 回归测试：简单无条件任务不受影响，复杂条件任务遇到 `UNKNOWN` 会明确中止。
- 回退策略：不自动回退到旧的扁平盲跑链路，失败时直接报明原因。

## 分阶段落地
1. 先做条件识别、DSL、校验与拦截。
2. 再支持文字可见类条件自动执行。
3. 最后支持高置信度字段空/非空条件执行。
4. 后续再扩展更复杂的 UI 状态条件。

## 成功标准
- 条件句不再被静默压平成危险线性步骤。
- 用户原文中的关键值和关键动作不会丢失。
- `input` 不再在未知焦点下直接输入。
- `UNKNOWN` 时能安全中止并给出明确原因。
- 简单无条件任务链路不回归。
