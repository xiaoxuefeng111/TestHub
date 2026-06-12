# Mobile Conditional DSL Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为移动端 AI 自动化实现通用 UI 条件句框架，让自然语言中的条件语义先结构化、再校验、后执行，并在不安全时明确中止。

**Architecture:** 复用 `ai_base.py` 的步骤抽取与字面值保留能力，新增 `mobile_semantic_parser.py`、`mobile_plan_validator.py`、`mobile_condition_evaluator.py` 三个轻量模块；在 `mobile_agent.py` 里接入 DSL 与校验链路，在 `ui_flow_runner.py` 里补最小输入聚焦、清空和条件执行能力。

**Tech Stack:** Django、现有 OpenAI-compatible LLM、Airtest、EasyOCR、Android UI hierarchy helper、pytest。

---

### Task 1: 补 DSL 解析与校验的失败测试

**Files:**
- Create: `apps/ui_automation/tests/test_mobile_semantic_parser.py`
- Modify: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing test**
- 覆盖登录/交易条件句：账号为空分支、账号非空分支、关键按钮保真、关键值保真。
- 覆盖校验失败：`input` 缺目标、关键值丢失、关键按钮丢失、条件分支缺失。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py -k "semantic or validator or conditional" -v`

**Step 3: Write minimal implementation**
- 先只让测试红灯定位到缺失模块和缺失行为。

**Step 4: Run test to verify it still fails for the right reason**
- Run: `pytest apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py -k "semantic or validator or conditional" -v`

**Step 5: Commit**
- `git add apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py`
- `git commit -m "test: add mobile conditional dsl failing coverage"`

### Task 2: 实现语义解析器与计划校验器

**Files:**
- Create: `apps/ui_automation/mobile_semantic_parser.py`
- Create: `apps/ui_automation/mobile_plan_validator.py`
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_semantic_parser.py`

**Step 1: Implement parser with constrained DSL output**
- 先复用 `ai_base.py` 的步骤抽取能力。
- 加规则预分析，识别条件句与关键字面值。
- 在高风险条件句场景生成受限 DSL，保留 `unsafe_reason`。

**Step 2: Implement validator**
- 校验关键值保真、关键按钮保真、`input` 完整性、条件分支完整性。

**Step 3: Wire parser + validator into mobile planner**
- 在 `MobileFlowPlanner` 中新增 DSL 生成与校验入口。
- 失败时返回明确错误，不降级到危险扁平执行。

**Step 4: Run tests**
- Run: `pytest apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py -k "semantic or validator or conditional" -v`

**Step 5: Commit**
- `git add apps/ui_automation/mobile_semantic_parser.py apps/ui_automation/mobile_plan_validator.py apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py`
- `git commit -m "feat: add mobile conditional dsl parser and validator"`

### Task 3: 为执行层补最小条件求值与输入安全能力

**Files:**
- Create: `apps/ui_automation/mobile_condition_evaluator.py`
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Modify: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Write/extend failing tests**
- 条件求值返回 `TRUE/FALSE/UNKNOWN` 的分支行为。
- `focus_field` 会先聚焦。
- `input(clear_first=true)` 会先清空再输入。
- `UNKNOWN` 时会中止，不进入任一分支。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 3: Write minimal implementation**
- 新增条件求值器。
- `UiFlowRunner` 新增条件节点执行入口、分支日志、`focus_field` 和 `clear_first` 支持。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 5: Commit**
- `git add apps/ui_automation/mobile_condition_evaluator.py apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- `git commit -m "feat: add safe conditional execution for mobile ui flow"`

### Task 4: 打通 mobile agent 到 runner 的 DSL 下放链路

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Modify: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing test**
- 命中条件 DSL 时，planner 不再只返回扁平 `ui_flow`，而是返回带条件的执行计划或安全失败。
- 登录/交易示例中，`交易登录` 不会被丢失。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/ui_automation/tests/test_mobile_agent.py -k "conditional or planner" -v`

**Step 3: Write minimal implementation**
- 在 planner / executor 之间增加 DSL 到 runner 步骤的下放逻辑。
- 仅放行 V1 支持的条件类型。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/ui_automation/tests/test_mobile_agent.py -k "conditional or planner" -v`

**Step 5: Commit**
- `git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py`
- `git commit -m "feat: wire mobile conditional dsl into planner flow"`

### Task 5: 端到端回归与文档收口

**Files:**
- Modify: `docs/plans/2026-06-11-mobile-conditional-dsl-design.md`
- Modify: `docs/plans/2026-06-11-mobile-conditional-dsl-implementation.md`

**Step 1: Run focused backend verification**
- Run: `pytest apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 2: Run regression check for related mobile path**
- Run: `pytest apps/ui_automation/tests/test_ai_run_adhoc_mobile.py -v`

**Step 3: Document final behavior and known limits**
- 更新第一版支持范围、`UNKNOWN` 中止边界和未支持条件类型。

**Step 4: Re-run the focused suite**
- Run: `pytest apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py apps/ui_automation/tests/test_ai_run_adhoc_mobile.py -v`

**Step 5: Commit**
- `git add docs/plans/2026-06-11-mobile-conditional-dsl-design.md docs/plans/2026-06-11-mobile-conditional-dsl-implementation.md`
- `git commit -m "docs: finalize mobile conditional dsl implementation notes"`
