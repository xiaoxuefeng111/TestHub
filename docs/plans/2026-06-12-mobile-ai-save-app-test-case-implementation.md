# Mobile AI Save App Test Case Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 AI 智能测试中的一次成功移动端执行可以保存为 APP 自动化测试模块可直接复用的 `AppTestCase`。

**Architecture:** 先在 `AIExecutionRecord` 上增加 `ui_flow_snapshot` 和保存关联字段，再让移动端执行器固化真实 `ui_flow`。随后新增 `save_as_app_test_case` 后端 action、序列化状态字段和前端双保存入口，最后用后端单测与前端手工验证确保这条沉淀链路稳定可用。

**Tech Stack:** Django、Django REST Framework、Vue 3、Element Plus

---

### Task 1: 扩展 AIExecutionRecord 数据模型

**Files:**
- Modify: `apps/ui_automation/models.py`
- Create: `apps/ui_automation/migrations/0004_ai_execution_record_app_test_case_snapshot.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`

**Step 1: 写失败测试，描述新字段的默认行为**

在 `apps/ui_automation/tests/test_ai_execution_record_mobile.py` 新增断言：

- `ui_flow_snapshot` 默认是空列表；
- `saved_app_test_case` 默认是 `None`。

**Step 2: 运行单测确认失败**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected:
- 测试因字段不存在而失败。

**Step 3: 在模型中新增字段**

修改 `apps/ui_automation/models.py`：

- 给 `AIExecutionRecord` 增加 `ui_flow_snapshot = models.JSONField(default=list, blank=True, verbose_name=...)`
- 增加 `saved_app_test_case = models.ForeignKey('app_automation.AppTestCase', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_ai_execution_records', verbose_name=...)`

**Step 4: 生成迁移文件**

Run:
`python manage.py makemigrations ui_automation`

Expected:
- 生成仅包含上述两个字段的迁移文件。

**Step 5: 运行单测确认通过**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected:
- 新增字段相关测试 PASS。

**Step 6: Commit**

```bash
git add apps/ui_automation/models.py apps/ui_automation/migrations/0004_ai_execution_record_app_test_case_snapshot.py apps/ui_automation/tests/test_ai_execution_record_mobile.py
git commit -m "feat: add app test case snapshot fields to ai execution record"
```

---

### Task 2: 在移动端执行阶段保存真实 ui_flow_snapshot

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: 先写失败测试**

在 `apps/ui_automation/tests/test_mobile_agent.py` 新增测试：

- 当 `run_mobile_execution()` 拿到 `planner.generate_ui_flow()` 的结果后；
- 在调用 `UiFlowRunner.run()` 前，`execution_record.ui_flow_snapshot` 已写入与执行一致的 `ui_flow`。

**Step 2: 运行目标测试确认失败**

Run:
`python manage.py test apps.ui_automation.tests.test_mobile_agent.MobileExecutionTests -v 2`

Expected:
- 因 `ui_flow_snapshot` 未写入而失败。

**Step 3: 做最小实现**

修改 `apps/ui_automation/mobile_agent.py`：

- 在 `ui_flow = planner.generate_ui_flow(...)` 后，立即把深拷贝后的 `ui_flow` 赋给 `execution_record.ui_flow_snapshot`；
- 与 `planned_tasks`、`logs` 一起 `_safe_save(..., update_fields=[...])`；
- 在最终保存时确保 `ui_flow_snapshot` 不会被遗漏覆盖。

**Step 4: 运行测试确认通过**

Run:
`python manage.py test apps.ui_automation.tests.test_mobile_agent -v 2`

Expected:
- 新增测试与现有移动端执行测试全部 PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "feat: persist mobile ui flow snapshots on ai execution records"
```

---

### Task 3: 扩展 AIExecutionRecord 序列化字段与保存资格判断

**Files:**
- Modify: `apps/ui_automation/serializers.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`

**Step 1: 先写失败测试**

在 `apps/ui_automation/tests/test_ai_execution_record_mobile.py` 新增测试覆盖：

- `saved_app_test_case` ID 返回；
- `saved_app_test_case_name` 返回；
- `can_save_as_app_test_case` 在以下条件下为真：
  - `execution_mode='mobile'`
  - `status='passed'`
  - `ui_flow_snapshot` 非空
  - `saved_app_test_case` 为空

并补一个负例，例如 `status='failed'` 时返回 false。

**Step 2: 运行测试确认失败**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected:
- 新字段或资格判断缺失导致失败。

**Step 3: 实现序列化逻辑**

修改 `apps/ui_automation/serializers.py`：

- 新增只读字段 `saved_app_test_case_name`；
- 新增 `SerializerMethodField`：`can_save_as_app_test_case`；
- 把 `saved_app_test_case` 加入输出字段；
- 不把 `ui_flow_snapshot` 放入常规序列化字段。

**Step 4: 运行测试确认通过**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected:
- 序列化测试 PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/serializers.py apps/ui_automation/tests/test_ai_execution_record_mobile.py
git commit -m "feat: expose app test case save state on ai execution records"
```

---

### Task 4: 新增 ui_flow 清洗 helper

**Files:**
- Create: `apps/ui_automation/app_test_case_snapshot.py`
- Test: `apps/ui_automation/tests/test_app_test_case_snapshot.py`

**Step 1: 先写失败测试**

创建 `apps/ui_automation/tests/test_app_test_case_snapshot.py`，覆盖：

- 普通步骤字段白名单保留；
- 非白名单运行态字段会被移除；
- `if` 步骤里的 `then_steps` / `else_steps` 会递归清洗；
- 顶层返回结构仍为 list。

**Step 2: 运行测试确认失败**

Run:
`python manage.py test apps.ui_automation.tests.test_app_test_case_snapshot -v 2`

Expected:
- 因 helper 文件尚不存在而失败。

**Step 3: 实现最小 helper**

创建 `apps/ui_automation/app_test_case_snapshot.py`：

- 提供类似 `sanitize_ui_flow_snapshot(ui_flow: list) -> list` 的函数；
- 采用显式白名单；
- 对 `then_steps` / `else_steps` 递归调用自己；
- 对非法结构返回空列表或过滤后的安全结构。

**Step 4: 运行测试确认通过**

Run:
`python manage.py test apps.ui_automation.tests.test_app_test_case_snapshot -v 2`

Expected:
- 清洗 helper 测试 PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/app_test_case_snapshot.py apps/ui_automation/tests/test_app_test_case_snapshot.py
git commit -m "feat: add ui flow snapshot sanitizer for app test case saving"
```

---

### Task 5: 新增保存为 APP 测试用例后端接口

**Files:**
- Modify: `apps/ui_automation/views.py`
- Test: `apps/ui_automation/tests/test_ai_save_as_app_test_case.py`
- Reference: `apps/app_automation/models.py`

**Step 1: 先写失败测试**

创建 `apps/ui_automation/tests/test_ai_save_as_app_test_case.py`，覆盖以下场景：

- 成功的移动端记录可创建 `AppTestCase`；
- 返回 `already_saved=false`；
- 再次调用时不重复创建，返回 `already_saved=true`；
- `status != passed` 时返回 400；
- `ui_flow_snapshot` 为空时返回 400；
- `execution_mode != mobile` 时返回 400。

**Step 2: 运行测试确认失败**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_save_as_app_test_case -v 2`

Expected:
- 因 action 不存在而失败。

**Step 3: 实现 detail action**

修改 `apps/ui_automation/views.py`：

- 在 `AIExecutionRecordViewSet` 中新增 `@action(detail=True, methods=['post'], url_path='save_as_app_test_case')`；
- 校验记录状态与快照；
- 若 `saved_app_test_case` 已存在则直接返回；
- 通过 `sanitize_ui_flow_snapshot()` 清洗快照；
- 创建 `AppTestCase`；
- 回写 `saved_app_test_case`；
- 返回 `already_saved` 和 `app_test_case` 简要信息。

**Step 4: 运行测试确认通过**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_save_as_app_test_case -v 2`

Expected:
- 新接口测试 PASS。

**Step 5: 补跑相关回归**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_run_adhoc_mobile -v 2`

Expected:
- AI 移动端相关回归 PASS。

**Step 6: Commit**

```bash
git add apps/ui_automation/views.py apps/ui_automation/tests/test_ai_save_as_app_test_case.py apps/ui_automation/app_test_case_snapshot.py
 git commit -m "feat: save successful mobile ai runs as app test cases"
```

---

### Task 6: 新增前端 API 封装

**Files:**
- Modify: `frontend/src/api/ui_automation.js`

**Step 1: 先写最小调用设计**

在实现前明确前端需要两个接口：

- 现有 `createAICase()` 继续用于“保存为 AI 模板”；
- 新增 `saveAIExecutionAsAppTestCase(id, data)` 调用 `/ui-automation/ai-execution-records/{id}/save_as_app_test_case/`。

**Step 2: 实现 API 函数**

修改 `frontend/src/api/ui_automation.js`：

- 新增 `saveAIExecutionAsAppTestCase`；
- 保持与现有 request 风格一致。

**Step 3: 可选快速校验**

Run:
`npm run lint`

Workdir:
`frontend`

Expected:
- 无新增 API 语法错误。

**Step 4: Commit**

```bash
git add frontend/src/api/ui_automation.js
git commit -m "feat: add api for saving ai execution as app test case"
```

---

### Task 7: 改造 AI 测试页双保存入口

**Files:**
- Modify: `frontend/src/views/ui-automation/ai/AITesting.vue`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`
- Reference: `frontend/src/router/index.js`

**Step 1: 先做交互拆分设计落地**

页面上把当前单一“保存为用例”拆成两类：

- `保存为 AI 模板`
- `保存为 APP 测试用例`

并新增 APP 测试用例保存弹窗与状态。

**Step 2: 实现页面状态字段**

在 `AITesting.vue` 中新增：

- 当前执行记录详情状态，如 `currentExecutionRecord`；
- `canSaveAsAppTestCase` 计算属性；
- APP 测试用例保存弹窗状态与表单；
- 保存成功后的跳转逻辑。

**Step 3: 修改轮询逻辑**

在 `pollLogs()` 中：

- 除了 `logs` 与 `planned_tasks`，还同步记录 `status`、`saved_app_test_case`、`can_save_as_app_test_case`；
- 成功后自动启用 APP 测试用例保存按钮。

**Step 4: 接入新接口**

- “保存为 AI 模板”继续调用 `createAICase()`；
- “保存为 APP 测试用例”调用 `saveAIExecutionAsAppTestCase(currentExecutionId, payload)`；
- 成功后跳转 `/app-automation/test-cases`。

**Step 5: 更新中英文文案**

在两个 locale 文件里新增：

- `saveAsAITemplate`
- `saveAsAppTestCase`
- `saveAsAppTestCaseTitle`
- `alreadySavedAppTestCase`
- `goToAppTestCases`
- `unsupportedSaveAsAppTestCase`
- 相关 success / failed / disabled 文案

**Step 6: 运行前端校验**

Run:
`npm run lint`

Workdir:
`frontend`

Expected:
- `AITesting.vue` 与 locale 修改无 lint 错误。

**Step 7: Commit**

```bash
git add frontend/src/views/ui-automation/ai/AITesting.vue frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/ui-automation.js frontend/src/api/ui_automation.js
git commit -m "feat: split ai template save and app test case save flows"
```

---

### Task 8: 在 AI 执行记录页补充沉淀入口

**Files:**
- Modify: `frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`

**Step 1: 先加失败/禁用态规则**

在记录列表和详情弹窗上，根据返回字段控制：

- `保存为 APP 测试用例`
- `查看 APP 测试用例`
- 不支持时展示禁用/提示

**Step 2: 实现操作列与详情页按钮**

在 `AIExecutionRecords.vue`：

- 给满足条件的记录增加保存入口；
- 已保存记录可直接跳转 `AppTestCaseList`；
- 失败记录或无快照记录不可触发保存。

**Step 3: 复用保存弹窗/逻辑**

尽量抽共用方法，避免与 `AITesting.vue` 复制大量相同代码。

**Step 4: 运行前端校验**

Run:
`npm run lint`

Workdir:
`frontend`

Expected:
- 执行记录页无 lint 错误。

**Step 5: Commit**

```bash
git add frontend/src/views/ui-automation/ai/AIExecutionRecords.vue frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/ui-automation.js
git commit -m "feat: add app test case save entry to ai execution records"
```

---

### Task 9: 做整体验证与文档收尾

**Files:**
- Modify: `docs/plans/2026-06-12-mobile-ai-save-app-test-case-design.md`（如需补充实现偏差说明）
- Modify: `docs/plans/2026-06-12-mobile-ai-save-app-test-case-implementation.md`

**Step 1: 跑后端测试集**

Run:
`python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_run_adhoc_mobile apps.ui_automation.tests.test_ai_save_as_app_test_case apps.ui_automation.tests.test_app_test_case_snapshot -v 2`

Expected:
- 新增后端相关测试全部 PASS。

**Step 2: 跑前端 lint**

Run:
`npm run lint`

Workdir:
`frontend`

Expected:
- 前端无 lint 错误。

**Step 3: 手工验证主链路**

手工验证以下路径：

1. 打开 `AI 智能测试` 页面；
2. 选择 Android 设备与应用包；
3. 输入自然语言任务并跑通；
4. 点击 `保存为 APP 测试用例`；
5. 跳转到 `/app-automation/test-cases`；
6. 确认新用例存在；
7. 选择设备执行，确认可启动应用并进入流程。

**Step 4: 记录验证结果**

若实现与设计有偏差，在设计文档末尾补一段“Implementation Notes”。

**Step 5: Commit**

```bash
git add docs/plans/2026-06-12-mobile-ai-save-app-test-case-design.md docs/plans/2026-06-12-mobile-ai-save-app-test-case-implementation.md
git commit -m "docs: finalize mobile ai app test case save plan"
```
