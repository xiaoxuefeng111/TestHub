# AI 执行成功后沉淀为 APP 正式测试用例设计

> **Goal:** 让 AI 智能测试在移动端成功执行后，可以通过确认弹框将这次真实跑通的 UI Flow 沉淀为 `AppTestCase`，后续可在 APP 自动化模块中直接复用、编辑和执行。
>
> **Architecture:** 在 `AIExecutionRecord` 中持久化本次移动端实际执行的 `executed_ui_flow`，并新增“已生成正式用例”的关联字段。成功执行后由前端发起 `save_as_app_test_case` 请求，后端直接将真实执行的 flow 转成 `AppTestCase.ui_flow`，前端再给出“去编辑 / 暂不处理”的二次选择。
>
> **Tech Stack:** Django ORM、Django REST Framework、Vue 3、Element Plus

---

## 1. 背景与问题

当前仓库已经具备两套相邻但未闭环的能力：

1. `frontend/src/views/ui-automation/ai/AITesting.vue` 可以发起移动端 AI 智能测试。
2. `apps/ui_automation/mobile_agent.py` 会把自然语言任务生成结构化 `ui_flow`，并交给 `UiFlowRunner` 执行。
3. `apps/app_automation/models.py` 中的 `AppTestCase` 已经是 APP 自动化模块的正式测试用例载体。

问题在于：

- 当前“保存为用例”保存的是 `AICase`，本质上只是自然语言模板。
- `AICase` 不包含本次真实跑通的结构化步骤。
- 成功执行后的结果无法直接沉淀为 `AppTestCase`，也就无法做到“成功一次，后续直接复用”。

本次设计要补上的就是这条闭环：

> **AI 移动端执行成功后，基于本次真实跑通的 UI Flow，生成正式 APP 测试用例。**

---

## 2. 已确认的产品决策

以下决策已经在对话中确认，后续实现不再回退：

1. **仅在执行成功后触发沉淀**
   - 只针对 `execution_mode = mobile` 且 `status = passed` 的执行记录。
   - 失败、停止、不完整执行不提供自动沉淀入口。

2. **先弹确认框，再生成正式测试用例**
   - 不自动落库。
   - 由用户确认是否把这次成功执行沉淀为正式用例。

3. **以本次真实执行的实际 UI Flow 为准**
   - 不再根据自然语言二次推理。
   - 不从 `planned_tasks`、`steps_completed` 或日志反推。

4. **账号、密码等输入值按本次实际值原样保存**
   - V1 不做变量抽取。
   - `variables` 先留空数组。

5. **确认框里允许修改用例名和描述**
   - 默认自动带出，但用户可以手动调整后再保存。

6. **保存成功后再弹结果框**
   - 提供两个动作：`去编辑正式测试用例` / `暂不处理`。
   - 不强制跳转。

7. **执行记录页保留兜底入口**
   - 即使用户错过了首次弹框，也可以在执行记录详情中补生成。

---

## 3. 用户流程

### 3.1 首次成功后的主流程

1. 用户在 `AITesting` 页面选择设备、应用包，输入自然语言任务。
2. 前端调用 `/ui-automation/ai-execution-records/run_adhoc/`，以 `execution_mode=mobile` 发起执行。
3. `mobile_agent.py` 生成真实 `ui_flow` 并执行。
4. 执行状态变为 `passed` 后，前端检测到本轮成功结束。
5. 前端弹出“生成正式测试用例”确认框，表单中预填：
   - 用例名称
   - 用例描述
   - 当前应用包（只展示）
6. 用户确认后，前端调用：
   - `POST /ui-automation/ai-execution-records/{id}/save_as_app_test_case/`
7. 后端基于本次真实执行的 `executed_ui_flow` 创建 `AppTestCase`。
8. 前端弹出结果框：
   - `去编辑正式测试用例`
   - `暂不处理`
9. 如果选择“去编辑”，则跳转到：
   - `/app-automation/scene-builder?case_id=<app_test_case_id>`

### 3.2 兜底流程

如果用户关闭了首次确认框，后续仍可在 `AIExecutionRecords` 页面对同一条成功记录点击：

- `生成正式测试用例`

只要该记录尚未生成正式用例，就可以补生成。

---

## 4. 数据模型设计

### 4.1 `AIExecutionRecord` 新增字段

文件：`apps/ui_automation/models.py`

为 `AIExecutionRecord` 新增两个字段：

1. `executed_ui_flow = models.JSONField(default=list, blank=True, ...)`
   - 保存本次移动端 AI 真正执行的结构化 flow。
   - 这是后续生成正式用例的唯一可信数据源。

2. `generated_app_test_case = models.ForeignKey('app_automation.AppTestCase', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_ai_execution_records', ...)`
   - 表示这条成功执行记录是否已经沉淀出正式用例。
   - 用于幂等控制和前端按钮状态判断。

### 4.2 `AppTestCase` 使用策略

文件：`apps/app_automation/models.py`

V1 不修改 `AppTestCase` schema，而是直接复用现有字段：

- `name`
- `description`
- `app_package`
- `ui_flow`
- `variables`
- `timeout`
- `retry_count`
- `created_by`

### 4.3 项目字段策略

当前两边项目模型不同：

- AI 执行记录使用 `UiProject`
- APP 正式用例使用 `AppProject`

V1 不做跨模型自动映射，因此：

- `AppTestCase.project = null`

后续如果需要再单独加“选择归属项目”功能。

---

## 5. 后端接口设计

### 5.1 接口定义

`POST /ui-automation/ai-execution-records/{id}/save_as_app_test_case/`

### 5.2 请求体

```json
{
  "name": "登录并进入交易页",
  "description": "AI 成功执行后沉淀的正式测试用例"
}
```

### 5.3 服务端校验

按以下顺序校验：

1. 记录存在且当前用户可访问。
2. `execution_mode == 'mobile'`
3. `status == 'passed'`
4. `app_package` 不为空
5. `executed_ui_flow` 非空
6. `name` 非空

### 5.4 幂等规则

如果 `generated_app_test_case` 已存在：

- 不重复创建
- 直接返回已有用例信息
- `already_generated = true`

首次成功创建则返回：

- `already_generated = false`
- `app_test_case_id`
- `app_test_case_name`

### 5.5 创建映射

创建 `AppTestCase` 时字段映射如下：

- `name` ← 用户确认后的名称
- `description` ← 用户确认后的描述
- `app_package` ← `AIExecutionRecord.app_package`
- `ui_flow` ← `{ "steps": executed_ui_flow }`
- `variables` ← `[]`
- `project` ← `null`
- `created_by` ← 当前用户
- `timeout` / `retry_count` ← 模型默认值

---

## 6. UI Flow 固化与转换策略

### 6.1 保存时机

文件：`apps/ui_automation/mobile_agent.py`

在 `planner.generate_ui_flow(...)` 返回后、`UiFlowRunner.run(...)` 调用前，立即执行：

- `execution_record.executed_ui_flow = ui_flow`

然后与 `planned_tasks`、`logs` 一起保存。

### 6.2 为什么必须在执行前固化

因为这份 `ui_flow` 同时满足：

- 已经过自然语言解析和归一化
- 真正用于本次执行
- 与后续日志、任务进度一一对应

它比原始文本、任务拆分摘要、执行后日志都更适合作为正式测试用例的来源。

### 6.3 保存策略

本次设计采用：

- **直接复用真实执行 flow**
- **不做二次推理**
- **不做失败后补偿式重建**

V1 只做必要的结构兼容处理：

- `AppTestCase.ui_flow` 统一保存为 `{ "steps": [...] }`

这样可以同时兼容现有正式用例执行器与 SceneBuilder。

---

## 7. 前端交互设计

### 7.1 `AITesting.vue`

文件：`frontend/src/views/ui-automation/ai/AITesting.vue`

新增三块行为：

1. **成功后自动弹确认框**
   - 仅本轮执行成功时触发一次
   - 若记录已生成正式用例，则不再弹

2. **确认框表单**
   - 用例名称：可编辑
   - 用例描述：可编辑
   - 应用包：只展示

3. **生成成功后的结果框**
   - 去编辑正式测试用例
   - 暂不处理

### 7.2 `AIExecutionRecords.vue`

文件：`frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`

新增兜底入口：

- 在详情弹框或操作列中增加：`生成正式测试用例`

按钮显示条件：

- 记录是 `mobile + passed`
- 且尚未生成正式用例

### 7.3 跳转目标

文件：`frontend/src/views/app-automation/test-cases/SceneBuilder.vue`

当前页面已支持：

- `route.query.case_id`
- 通过 `getTestCaseDetail(case_id)` 加载已有用例

因此生成成功后可以直接跳转：

- `/app-automation/scene-builder?case_id=<id>`

无需额外改造编辑页入口协议。

---

## 8. 测试与验收标准

### 8.1 后端测试

至少覆盖：

1. `AIExecutionRecord` 新字段默认值
2. 移动端执行时 `executed_ui_flow` 成功落库
3. `save_as_app_test_case` 首次生成成功
4. 重复调用时幂等返回
5. 非 `passed` / 非 `mobile` / 空 flow / 空 app_package` 的拒绝逻辑

### 8.2 前端验证

至少验证：

1. AI 页面成功后弹确认框
2. 可修改名称和描述
3. 点击确认后生成正式用例
4. 生成成功后弹二次结果框
5. 点击“去编辑”能跳转到 `SceneBuilder` 并加载用例
6. AI 执行记录页可补生成

### 8.3 最终验收标准

满足以下五条即视为 V1 完成：

1. 成功执行后会弹出“生成正式测试用例”确认框
2. 正式用例基于真实执行 `ui_flow` 生成
3. 正式用例可在 APP 测试用例列表中看到
4. 正式用例可进入 `SceneBuilder` 编辑
5. 正式用例可再次执行

---

## 9. 非目标与延后事项

V1 明确不做：

- 密码/账号自动变量化
- `UiProject -> AppProject` 自动映射
- 失败执行沉淀
- 历史执行记录回填 `executed_ui_flow`
- 多次成功执行自动合并为一个正式用例
- 用例去重、版本管理、差异比较

这些都可以在正式沉淀链路稳定后再扩展。