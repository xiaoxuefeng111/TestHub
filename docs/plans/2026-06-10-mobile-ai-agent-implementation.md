# Mobile AI Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让现有 AI 智能测试页面支持 Android 真机自主执行，自然语言任务可转为 OCR 驱动的手机操作并回传执行记录。

**Architecture:** 复用 `ui_automation` 的 AI 记录与轮询页面，新增 mobile 分支路由到 `app_automation` 能力。执行层采用“LLM 生成受限 ui_flow + UiFlowRunner OCR 动作 + Airtest 真机执行”。

**Tech Stack:** Django REST Framework、Vue 3 + Element Plus、Airtest、EasyOCR、现有 OpenAI-compatible LLM 配置。

---

### Task 1: 为 AI 执行记录补充移动端字段与序列化

**Files:**
- Modify: `apps/ui_automation/models.py`
- Modify: `apps/ui_automation/serializers.py`
- Create: `apps/ui_automation/migrations/0003_ai_execution_record_mobile_fields.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`

**Step 1: Write the failing test**
- 断言 `AIExecutionRecordSerializer` 能输出 `app_device_name`、`app_device_serial`、`app_package_name`。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/ui_automation/tests/test_ai_execution_record_mobile.py -v`

**Step 3: Write minimal implementation**
- `execution_mode` 增加 `mobile`
- 新增 `app_device`、`app_package`
- 序列化补充只读展示字段

**Step 4: Run test to verify it passes**
- Run: `pytest apps/ui_automation/tests/test_ai_execution_record_mobile.py -v`

**Step 5: Commit**
- `git add apps/ui_automation/models.py apps/ui_automation/serializers.py apps/ui_automation/migrations/0003_ai_execution_record_mobile_fields.py apps/ui_automation/tests/test_ai_execution_record_mobile.py`
- `git commit -m "feat: add mobile fields to ai execution record"`

### Task 2: 为 UiFlowRunner 增加 OCR 文字动作

**Files:**
- Modify: `apps/app_automation/utils/ocr_helper.py`
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Create: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Write the failing test**
- 测试 `tap_text` 能根据 OCR 返回的 bbox 点击中心点。
- 测试 `wait_text` 在命中时通过、超时时抛错。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 3: Write minimal implementation**
- OCR Helper 补充全文识别/查字定位方法
- Runner 增加 `start_app`、`tap_text`、`wait_text`、`swipe_until_text`、`keyevent`、`assert_text_visible`

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 5: Commit**
- `git add apps/app_automation/utils/ocr_helper.py apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- `git commit -m "feat: add ocr-driven mobile ui flow actions"`

### Task 3: 新增 Mobile Executor 与 AI flow 生成器

**Files:**
- Create: `apps/ui_automation/mobile_agent.py`
- Modify: `apps/ui_automation/views.py`
- Create: `apps/ui_automation/tests/test_ai_run_adhoc_mobile.py`

**Step 1: Write the failing test**
- `run_adhoc` 传入 `execution_mode=mobile`、`device_id`、`app_package_id` 时：
  - 创建 mobile 记录
  - 调起后台线程
  - 缺字段返回 400

**Step 2: Run test to verify it fails**
- Run: `pytest apps/ui_automation/tests/test_ai_run_adhoc_mobile.py -v`

**Step 3: Write minimal implementation**
- 新增 Mobile Agent：
  - 复用 `BaseBrowserAgent.analyze_task()` 或同源 prompt 生成 planned tasks
  - 再生成受限 `ui_flow`
  - 连接设备、执行 flow、更新日志与状态
- `run_adhoc` 分流到 mobile executor

**Step 4: Run test to verify it passes**
- Run: `pytest apps/ui_automation/tests/test_ai_run_adhoc_mobile.py -v`

**Step 5: Commit**
- `git add apps/ui_automation/mobile_agent.py apps/ui_automation/views.py apps/ui_automation/tests/test_ai_run_adhoc_mobile.py`
- `git commit -m "feat: support mobile ai adhoc execution"`

### Task 4: 前端 AI 测试页接入设备与应用包选择

**Files:**
- Modify: `frontend/src/views/ui-automation/ai/AITesting.vue`
- Modify: `frontend/src/api/ui_automation.js`
- Modify: `frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`

**Step 1: Write the failing test**
- 如果前端没有测试框架，则先通过静态检查保证：
  - 提交参数包含 `device_id`、`app_package_id`、`execution_mode=mobile`
  - 页面存在设备/应用包选择 UI

**Step 2: Run test to verify it fails**
- Run: `npm run lint -- frontend/src/views/ui-automation/ai/AITesting.vue`

**Step 3: Write minimal implementation**
- 复用 `app-automation.js` 的设备/应用包接口
- 页面新增 Android 设备与应用包下拉
- 记录页详情展示设备/应用包信息

**Step 4: Run test to verify it passes**
- Run: `npm run lint -- frontend/src/views/ui-automation/ai/AITesting.vue frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`

**Step 5: Commit**
- `git add frontend/src/views/ui-automation/ai/AITesting.vue frontend/src/api/ui_automation.js frontend/src/views/ui-automation/ai/AIExecutionRecords.vue frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/ui-automation.js`
- `git commit -m "feat: add mobile context to ai testing page"`

### Task 5: 全链路验证

**Files:**
- Modify: `docs/plans/2026-06-10-mobile-ai-agent-design.md`
- Modify: `docs/plans/2026-06-10-mobile-ai-agent-implementation.md`

**Step 1: Run backend tests**
- Run: `pytest apps/ui_automation/tests/test_ai_run_adhoc_mobile.py apps/ui_automation/tests/test_ai_execution_record_mobile.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

**Step 2: Run targeted frontend checks**
- Run: `npm run lint -- frontend/src/views/ui-automation/ai/AITesting.vue frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`

**Step 3: Smoke-check no regression in existing app executor**
- Run: `pytest apps/app_automation/tests/test_app_executor.py -v`

**Step 4: Update docs if implementation drifted**
- 记录最终范围、限制和后续建议

**Step 5: Commit**
- `git add docs/plans/2026-06-10-mobile-ai-agent-design.md docs/plans/2026-06-10-mobile-ai-agent-implementation.md`
- `git commit -m "docs: finalize mobile ai agent plan"`
