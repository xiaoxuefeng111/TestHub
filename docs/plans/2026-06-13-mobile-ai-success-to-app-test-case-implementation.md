# Mobile AI Success To App Test Case Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让移动端 AI 智能测试在成功执行后，可以由用户确认并沉淀为可直接复用、编辑、再次执行的 `AppTestCase`。

**Architecture:** 先在 `AIExecutionRecord` 上新增真实执行 flow 快照和正式用例关联字段，再在移动端执行链路中固化 `executed_ui_flow`。随后新增 `save_as_app_test_case` 后端 action，并在前端 AI 测试页与执行记录页加入确认弹框和兜底入口，最后用 Django 测试和手工回归验证整条沉淀链路。

**Tech Stack:** Django、Django REST Framework、Vue 3、Element Plus

---

### Task 1: 扩展 AIExecutionRecord 模型以承载真实 flow 和生成结果

**Files:**
- Modify: `apps/ui_automation/models.py`
- Create: `apps/ui_automation/migrations/0004_ai_execution_record_generated_case_fields.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`

**Step 1: Write the failing test**

在 `apps/ui_automation/tests/test_ai_execution_record_mobile.py` 新增断言：

```python
record = AIExecutionRecord.objects.create(
    case_name="demo",
    task_description="打开应用并登录",
)
assert record.executed_ui_flow == []
assert record.generated_app_test_case is None
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected: FAIL，提示新字段不存在或序列化缺失。

**Step 3: Write minimal implementation**

在 `apps/ui_automation/models.py` 的 `AIExecutionRecord` 中新增：

```python
executed_ui_flow = models.JSONField(default=list, blank=True, verbose_name='实际执行UI Flow')
generated_app_test_case = models.ForeignKey(
    'app_automation.AppTestCase',
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name='source_ai_execution_records',
    verbose_name='生成的正式测试用例',
)
```

**Step 4: Generate migration**

Run: `python manage.py makemigrations ui_automation`

Expected: 生成仅包含以上两个字段的 migration。

**Step 5: Run test to verify it passes**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected: PASS。

**Step 6: Commit**

```bash
git add apps/ui_automation/models.py apps/ui_automation/migrations/0004_ai_execution_record_generated_case_fields.py apps/ui_automation/tests/test_ai_execution_record_mobile.py
git commit -m "feat: add mobile ai execution snapshot fields"
```

---

### Task 2: 在移动端执行链路中持久化真实 executed_ui_flow

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing test**

在 `apps/ui_automation/tests/test_mobile_agent.py` 新增测试，验证：

```python
run_mobile_execution(execution_record_id=record.id, should_stop=lambda: False)
record.refresh_from_db()
assert record.executed_ui_flow == expected_ui_flow
```

其中 `expected_ui_flow` 使用 mocked `planner.generate_ui_flow()` 返回值。

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.ui_automation.tests.test_mobile_agent -v 2`

Expected: FAIL，`executed_ui_flow` 仍为空。

**Step 3: Write minimal implementation**

在 `apps/ui_automation/mobile_agent.py` 中，紧跟在：

```python
ui_flow = planner.generate_ui_flow(...)
```

之后加入：

```python
execution_record.executed_ui_flow = ui_flow
```

并在首次 `_safe_save(...)` 中把 `executed_ui_flow` 加进 `update_fields`。

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.ui_automation.tests.test_mobile_agent -v 2`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "feat: persist executed mobile ui flow"
```

---

### Task 3: 扩展 AIExecutionRecord 序列化结果供前端判断生成状态

**Files:**
- Modify: `apps/ui_automation/serializers.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`

**Step 1: Write the failing test**

新增序列化测试：

```python
data = AIExecutionRecordSerializer(instance=record).data
assert data["generated_app_test_case_id"] is None
assert data["can_generate_app_test_case"] is True
```

再补一个反例：`status='failed'` 时应为 `False`。

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected: FAIL，返回字段不存在。

**Step 3: Write minimal implementation**

在 `apps/ui_automation/serializers.py` 中新增：

```python
generated_app_test_case_id = serializers.IntegerField(source='generated_app_test_case.id', read_only=True)
can_generate_app_test_case = serializers.SerializerMethodField()
```

并实现：

```python
def get_can_generate_app_test_case(self, obj):
    return (
        obj.execution_mode == 'mobile'
        and obj.status == 'passed'
        and bool(obj.executed_ui_flow)
        and obj.generated_app_test_case_id is None
    )
```

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile -v 2`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/serializers.py apps/ui_automation/tests/test_ai_execution_record_mobile.py
git commit -m "feat: expose app test case generation state"
```

---

### Task 4: 新增执行结果到 AppTestCase 的转换 helper

**Files:**
- Create: `apps/ui_automation/app_test_case_builder.py`
- Test: `apps/ui_automation/tests/test_app_test_case_builder.py`

**Step 1: Write the failing test**

创建 `apps/ui_automation/tests/test_app_test_case_builder.py`，至少覆盖：

```python
flow = [{"type": "start_app", "package_name": "com.demo"}, {"type": "tap_text", "text": "登录"}]
result = build_app_test_case_ui_flow(flow)
assert result == {"steps": flow}
```

再补一个空 flow 反例：

```python
with pytest.raises(ValueError):
    build_app_test_case_ui_flow([])
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.ui_automation.tests.test_app_test_case_builder -v 2`

Expected: FAIL，helper 文件不存在。

**Step 3: Write minimal implementation**

创建 `apps/ui_automation/app_test_case_builder.py`：

```python
def build_app_test_case_ui_flow(executed_ui_flow):
    if not executed_ui_flow:
        raise ValueError("executed_ui_flow is empty")
    return {"steps": executed_ui_flow}
```

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.ui_automation.tests.test_app_test_case_builder -v 2`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/ui_automation/app_test_case_builder.py apps/ui_automation/tests/test_app_test_case_builder.py
git commit -m "feat: add app test case builder for ai executions"
```

---

### Task 5: 新增 save_as_app_test_case 后端 action

**Files:**
- Modify: `apps/ui_automation/views.py`
- Test: `apps/ui_automation/tests/test_ai_save_as_app_test_case.py`
- Reference: `apps/app_automation/models.py`

**Step 1: Write the failing test**

创建 `apps/ui_automation/tests/test_ai_save_as_app_test_case.py`，覆盖：

```python
response = self.client.post(url, {"name": "登录流程", "description": "AI成功沉淀"}, format="json")
self.assertEqual(response.status_code, 200)
self.assertEqual(AppTestCase.objects.count(), 1)
```

再补以下反例：
- `status != passed`
- `execution_mode != mobile`
- `executed_ui_flow == []`
- `app_package is None`

以及幂等例：第二次调用不重复创建。

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.ui_automation.tests.test_ai_save_as_app_test_case -v 2`

Expected: FAIL，action 不存在。

**Step 3: Write minimal implementation**

在 `AIExecutionRecordViewSet` 中新增：

```python
@action(detail=True, methods=['post'])
def save_as_app_test_case(self, request, pk=None):
    ...
```

核心逻辑：
- 校验记录状态
- 若已生成则直接返回
- 调 `build_app_test_case_ui_flow(record.executed_ui_flow)`
- 创建 `AppTestCase`
- 回写 `record.generated_app_test_case`

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.ui_automation.tests.test_ai_save_as_app_test_case -v 2`

Expected: PASS。

**Step 5: Run regression tests**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_run_adhoc_mobile -v 2`

Expected: 相关回归 PASS。

**Step 6: Commit**

```bash
git add apps/ui_automation/views.py apps/ui_automation/tests/test_ai_save_as_app_test_case.py apps/ui_automation/app_test_case_builder.py
git commit -m "feat: save successful ai executions as app test cases"
```

---

### Task 6: 新增前端 API 封装

**Files:**
- Modify: `frontend/src/api/ui_automation.js`

**Step 1: Define the new client call**

新增函数签名：

```javascript
export function saveAIExecutionAsAppTestCase(id, data) {
  return request({
    url: `/ui-automation/ai-execution-records/${id}/save_as_app_test_case/`,
    method: "post",
    data,
  });
}
```

**Step 2: Add the implementation**

在 `frontend/src/api/ui_automation.js` 中加入以上函数，保持与现有 API 风格一致。

**Step 3: Run lint to verify syntax**

Run: `npm run lint`

Workdir: `frontend`

Expected: 无新增语法错误。

**Step 4: Commit**

```bash
git add frontend/src/api/ui_automation.js
git commit -m "feat: add api for generating app test cases from ai runs"
```

---

### Task 7: 在 AITesting 页面加入成功后确认弹框和二次结果弹框

**Files:**
- Modify: `frontend/src/views/ui-automation/ai/AITesting.vue`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`

**Step 1: Write the UI state changes**

为 `AITesting.vue` 新增状态：

```javascript
const showGenerateDialog = ref(false)
const showGenerateSuccessDialog = ref(false)
const generateForm = reactive({ name: "", description: "" })
const generatedCaseId = ref(null)
```

**Step 2: Trigger the confirmation dialog after pass**

在轮询检测到：

```javascript
record.status === "passed"
```

时增加保护逻辑：
- 仅移动端执行
- 仅未生成正式用例
- 仅当前回合弹一次

然后打开“生成正式测试用例”弹框。

**Step 3: Submit the generation request**

弹框确认时调用：

```javascript
await saveAIExecutionAsAppTestCase(currentExecutionId.value, {
  name: generateForm.name,
  description: generateForm.description,
})
```

成功后记录 `generatedCaseId`，关闭第一层弹框，打开第二层结果弹框。

**Step 4: Add the success dialog actions**

“去编辑”按钮跳转：

```javascript
router.push({
  path: "/app-automation/scene-builder",
  query: { case_id: generatedCaseId.value },
})
```

“暂不处理”仅关闭弹框。

**Step 5: Add i18n strings**

补充文案：
- 生成正式测试用例
- 请输入正式用例名称
- 生成成功
- 去编辑
- 暂不处理
- 当前执行结果无法生成正式测试用例

**Step 6: Run lint to verify it passes**

Run: `npm run lint`

Workdir: `frontend`

Expected: PASS 或仅已有历史 warning。

**Step 7: Commit**

```bash
git add frontend/src/views/ui-automation/ai/AITesting.vue frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/ui-automation.js
git commit -m "feat: prompt to create app test cases after ai success"
```

---

### Task 8: 在 AIExecutionRecords 页面增加兜底生成入口

**Files:**
- Modify: `frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`

**Step 1: Add the manual action button**

在执行记录详情或操作列中增加：

```vue
<el-button v-if="row.can_generate_app_test_case" size="small" type="primary">
  生成正式测试用例
</el-button>
```

**Step 2: Reuse the same dialog flow**

实现与 `AITesting.vue` 一致的：
- 名称/描述确认弹框
- 成功后“去编辑 / 暂不处理”弹框

**Step 3: Wire the submit call**

复用：

```javascript
saveAIExecutionAsAppTestCase(row.id, { name, description })
```

**Step 4: Refresh the record after success**

创建成功后重新加载列表或更新当前记录，确保按钮消失。

**Step 5: Run lint to verify it passes**

Run: `npm run lint`

Workdir: `frontend`

Expected: PASS 或仅已有历史 warning。

**Step 6: Commit**

```bash
git add frontend/src/views/ui-automation/ai/AIExecutionRecords.vue frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/ui-automation.js
git commit -m "feat: add manual app test case generation in ai execution records"
```

---

### Task 9: 执行最终验证并记录结果

**Files:**
- Modify: `docs/plans/2026-06-13-mobile-ai-success-to-app-test-case-implementation.md`

**Step 1: Run backend tests**

Run: `python manage.py test apps.ui_automation.tests.test_ai_execution_record_mobile apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_save_as_app_test_case -v 2`

Expected: PASS。

**Step 2: Run frontend lint**

Run: `npm run lint`

Workdir: `frontend`

Expected: PASS 或仅已有历史 warning。

**Step 3: Perform manual end-to-end verification**

手工验证顺序：
1. 在 `AITesting` 发起一次真实移动端 AI 测试。
2. 等待执行成功。
3. 在确认框中修改用例名和描述并确认生成。
4. 在成功弹框中点击“去编辑”。
5. 检查 `SceneBuilder` 是否正确加载生成用例。
6. 返回 `/app-automation/test-cases`，确认列表中存在该用例。
7. 对该用例发起一次执行，确认链路可跑通。

**Step 4: Record verification notes**

把实际测试结果追加到本计划文档末尾，记录：
- 后端测试结果
- 前端 lint 结果
- 手工验证结果
- 剩余风险

**Step 5: Commit**

```bash
git add docs/plans/2026-06-13-mobile-ai-success-to-app-test-case-implementation.md
git commit -m "docs: record verification for ai success to app test case flow"
```
