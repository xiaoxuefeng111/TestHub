# 移动端 AI 成功执行保存为 APP 测试用例设计

> **Goal:** 将 AI 智能测试页面中的一次成功移动端执行，保存为可在 APP 自动化测试模块直接复用的 `AppTestCase`。
**Architecture:** 在 `AIExecutionRecord` 上补充真实 `ui_flow` 快照与保存关联字段；移动端执行时固化归一化后的 `ui_flow_snapshot`；成功后由 AI 执行记录提供“保存为 APP 测试用例”动作，直接创建 `AppTestCase`，前端保留“AI 模板”和“APP 测试用例”两条独立保存路径。
**Tech Stack:** Django ORM、Django REST Framework、Vue 3、Element Plus

---

## 1. 背景与问题

当前移动端 AI 临时执行链路已经具备这些能力：

- `frontend/src/views/ui-automation/ai/AITesting.vue` 可以提交自然语言任务、设备、应用包。
- `apps/ui_automation/views.py` 的 `run_adhoc` 在 `execution_mode=mobile` 时会创建 `AIExecutionRecord`。
- `apps/ui_automation/mobile_agent.py` 会基于自然语言生成结构化 `ui_flow`，再交给 `UiFlowRunner` 执行。
- `apps/app_automation/models.py` 里的 `AppTestCase` 本身就是 APP 自动化测试模块的可复用测试用例载体。

但当前“保存为用例”按钮保存的是 `AICase`：

- 保存的是自然语言任务模板；
- 不是本次真实成功执行过的结构化 `ui_flow`；
- 无法直接在 `APP 自动化测试 / 测试用例` 页面中复用。

因此，当前能力缺少一条关键闭环：

> **自然语言探索执行成功后，把“这次真实成功执行的结构化流程”沉淀成标准 `AppTestCase`。**

---

## 2. 目标与非目标

### 2.1 目标

V1 目标：

1. 用户在 AI 智能测试页输入自然语言任务。
2. 在真机上执行成功。
3. 用户点击 **保存为 APP 测试用例**。
4. 系统基于本次成功执行记录里的真实 `ui_flow` 创建 `AppTestCase`。
5. 用户进入 `/app-automation/test-cases` 后，选择设备即可直接执行。

### 2.2 非目标

本次不做：

- 从 `logs`、`steps_completed`、`planned_tasks` 反推测试用例；
- 为旧历史记录做 `ui_flow` 回填迁移；
- 强行把 `UiProject` 映射到 `AppProject`；
- 绑定具体执行设备；
- 改造 `AppTestCase` 编辑器；
- 支持失败执行记录保存为 APP 测试用例。

---

## 3. 方案对比

### 方案 A：沿用当前“保存为用例”，继续保存 `AICase`

**优点**
- 改动最小。

**缺点**
- 保存的是自然语言模板，不是可执行 `ui_flow`；
- 无法进入 APP 自动化测试模块直接复用；
- 无法保证“保存后真的能跑”。

**结论**
- 不满足目标，淘汰。

### 方案 B：成功后直接固化真实 `ui_flow` 为 `AppTestCase`（推荐）

**做法**
- 保留当前 `AICase` 保存路径，但明确改名为“保存为 AI 模板”；
- 新增“保存为 APP 测试用例”；
- 只允许针对成功执行记录保存；
- 保存源固定为该记录的 `ui_flow_snapshot`。

**优点**
- 语义清晰；
- 产物可直接复用；
- 不依赖重新推导，稳定性最高。

**缺点**
- 需要新增记录字段、保存动作和前端入口。

### 方案 C：保存时再根据自然语言重新生成一次 `ui_flow`

**优点**
- 理论上不用存快照。

**缺点**
- LLM 再生成结果可能漂移；
- 与本次真实成功执行流程不一致；
- 可用性最差。

**结论**
- 不建议采用。

---

## 4. 推荐方案总览

采用 **方案 B**，核心原则只有一条：

> **保存来源必须是本次真实执行时使用的结构化 `ui_flow` 快照，而不是任何反推结果。**

完整链路：

1. AI 移动端执行时生成归一化 `ui_flow`。
2. 后端把该 `ui_flow` 保存到 `AIExecutionRecord.ui_flow_snapshot`。
3. 执行成功后，前端允许触发 `save_as_app_test_case`。
4. 后端对 `ui_flow_snapshot` 做一次白名单清洗。
5. 创建 `AppTestCase`。
6. 将新建的测试用例回写到 `AIExecutionRecord.saved_app_test_case`。
7. 前端提示成功，并跳转到 `AppTestCaseList`。

---

## 5. 数据模型设计

### 5.1 `AIExecutionRecord` 新增字段

文件：`apps/ui_automation/models.py`

在 `AIExecutionRecord` 上新增两个字段：

1. `ui_flow_snapshot = models.JSONField(default=list, blank=True)`
   - 含义：本次移动端执行真正使用的结构化 `ui_flow` 快照；
   - 来源：`MobileFlowPlanner.generate_ui_flow()` 的归一化结果；
   - 用途：后续保存为 `AppTestCase` 的唯一可信来源。

2. `saved_app_test_case = models.ForeignKey('app_automation.AppTestCase', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_ai_execution_records')`
   - 含义：该执行记录是否已经沉淀出一个 APP 测试用例；
   - 用途：实现幂等保存，防止重复创建。

### 5.2 为什么不改 `AppTestCase` 表结构

V1 不新增来源字段到 `AppTestCase`：

- 当前目标是让用例可复用，而不是建立完整双向追踪图谱；
- `AIExecutionRecord.saved_app_test_case` 已足够实现“执行记录 -> 测试用例”的关联；
- 来源信息可以先写入 `description` 作为可见追踪元数据。

### 5.3 序列化返回建议

文件：`apps/ui_automation/serializers.py`

`AIExecutionRecordSerializer` 增加：

- `saved_app_test_case`（ID）
- `saved_app_test_case_name`
- `can_save_as_app_test_case`

其中：

- `ui_flow_snapshot` **不放进列表序列化字段**，避免详情/列表负载膨胀；
- `can_save_as_app_test_case = (execution_mode == 'mobile' and status == 'passed' and ui_flow_snapshot 非空 and saved_app_test_case 为空)`。

这样前端无须自行拼复杂判断，记录列表页也能直接知道按钮是否可点击。

---

## 6. `ui_flow_snapshot` 写入时机

文件：`apps/ui_automation/mobile_agent.py`

### 6.1 写入点

在 `run_mobile_execution()` 中：

1. `planner.generate_ui_flow(...)` 得到归一化 `ui_flow`；
2. 在调用 `UiFlowRunner.run(...)` 之前，立即深拷贝到 `execution_record.ui_flow_snapshot`；
3. 与 `planned_tasks`、`logs` 一起保存。

### 6.2 为什么要在执行前写入

因为这份 `ui_flow` 才是“本次执行准备真正使用的流程”：

- 已经过语义编译 / LLM 解析 / 归一化；
- 与 `planned_tasks` 一一对应；
- 不依赖执行成功后再回忆或重建。

即使本次执行失败，记录里也能保留真实快照；只是 **保存为 APP 测试用例** 仍然只对 `passed` 开放。

---

## 7. 保存接口设计

文件：`apps/ui_automation/views.py`

新增 detail action：

`POST /api/ui-automation/ai-execution-records/{id}/save_as_app_test_case/`

### 7.1 请求体

```json
{
  "name": "登录并进入交易页",
  "description": "AI 成功跑通后的固化用例"
}
```

### 7.2 服务端校验顺序

按以下顺序校验：

1. 记录存在且当前用户可访问；
2. `execution_mode == 'mobile'`；
3. `status == 'passed'`；
4. `ui_flow_snapshot` 非空；
5. 若 `saved_app_test_case` 已存在，则直接返回已保存结果；
6. 请求中的 `name` 非空。

### 7.3 幂等返回

第一次保存：

```json
{
  "success": true,
  "already_saved": false,
  "app_test_case": {
    "id": 123,
    "name": "登录并进入交易页"
  }
}
```

重复点击同一条记录：

```json
{
  "success": true,
  "already_saved": true,
  "app_test_case": {
    "id": 123,
    "name": "登录并进入交易页"
  }
}
```

---

## 8. `ui_flow` 清洗策略

### 8.1 为什么必须清洗

执行态 `ui_flow` 将来可能混入运行时字段，例如：

- OCR 命中结果；
- 实际点击坐标；
- 临时耗时；
- 运行态截图路径；
- 调试标记。

这些字段不应该直接落进 `AppTestCase.ui_flow`。

### 8.2 清洗原则

采用 **白名单递归清洗**，只保留可执行 DSL 字段。

建议保留的字段：

- 通用：`type`、`name`
- 启动：`package_name`、`wait_after`
- 文本识别：`text`、`match_mode`、`timeout`、`interval`、`index`、`region`
- 输入：`value`、`send_enter`
- 滑动：`direction`、`max_swipes`
- 按键：`keycode`
- 点击后验证：
  - `post_wait_text`
  - `post_wait_match_mode`
  - `post_wait_timeout`
  - `post_wait_interval`
  - `post_absent_text`
  - `post_absent_timeout`
  - `post_absent_interval`
- 条件分支：`condition`、`then_steps`、`else_steps`

### 8.3 条件步骤处理

`if` 步骤需要递归清洗 `then_steps` / `else_steps`，保证嵌套结构可继续执行。

### 8.4 不做反推修补

如果 `ui_flow_snapshot` 本身缺失或为空：

- 直接拒绝保存；
- 不尝试从 `planned_tasks`、`steps_completed`、`logs` 拼接恢复。

---

## 9. `AppTestCase` 创建映射

文件：`apps/ui_automation/views.py`

创建 `AppTestCase` 时字段映射如下：

- `name`：来自弹窗输入
- `description`：用户输入描述 + 来源附注
- `ui_flow`：清洗后的 `ui_flow_snapshot`
- `variables`：`[]`
- `project`：`null`
- `app_package`：`null`
- `timeout`：沿用模型默认值 `300`
- `retry_count`：沿用默认值 `0`
- `created_by`：当前登录用户

### 9.1 为什么 `project` 置空

- AI 模块当前使用的是 `UiProject`；
- APP 自动化模块使用的是 `AppProject`；
- 二者不是同一个模型，V1 不应该强行做映射。

### 9.2 为什么 `app_package` 置空仍可执行

因为移动端 AI 生成的 `ui_flow` 第一条本来就会包含：

- `type = start_app`
- `package_name = xxx`

因此：

- `AppTestCase.app_package` 不绑定，也不影响执行；
- 真正启动应用的信息已经内嵌在 `ui_flow` 中；
- 后续在 APP 测试页仍然是“选设备执行”，不是“复原原执行环境”。

### 9.3 来源附注建议

建议在 `description` 末尾追加：

- 来源执行记录 ID
- 原始自然语言任务
- 原始应用包名（仅供参考，不作为绑定字段）

这样无需再改 `AppTestCase` schema，也能保留基本溯源信息。

---

## 10. 前端交互设计

### 10.1 AI 测试页按钮分流

文件：`frontend/src/views/ui-automation/ai/AITesting.vue`

当前按钮：

- `开始执行`
- `停止执行`
- `保存为用例`

改造后：

- `开始执行`
- `停止执行`
- `保存为 AI 模板`
- `保存为 APP 测试用例`

### 10.2 状态规则

#### 保存为 AI 模板
- 保持现状；
- 只要任务描述非空即可使用；
- 仍然走 `createAICase`。

#### 保存为 APP 测试用例
- 仅当当前执行记录满足 `can_save_as_app_test_case=true` 时可点击；
- 如果该记录已保存，则显示“已保存”或“查看 APP 测试用例”。

### 10.3 绑定对象必须是执行记录

“保存为 APP 测试用例”必须绑定：

- `currentExecutionId`
- 或详情页中的某条 `AIExecutionRecord`

不能绑定当前输入框里的 `taskForm.description`。

因为用户在执行成功后可能继续修改输入框文本；
保存动作应该始终对应 **刚刚成功的那条真实执行记录**。

### 10.4 保存成功后的前端行为

建议交互：

1. 提示“保存成功”；
2. 提供“前往 APP 测试用例”快捷入口；
3. 可直接跳转到路由：`/app-automation/test-cases`。

---

## 11. 执行记录页补充入口

文件：`frontend/src/views/ui-automation/ai/AIExecutionRecords.vue`

除了 AI 测试页上的即时入口，再补一个次级入口：

- 在执行记录列表的操作列，为满足条件的记录显示 `保存为 APP 测试用例`；
- 若 `saved_app_test_case` 已存在，则显示 `查看 APP 测试用例`；
- 详情弹窗 footer 也可放同样按钮。

这样用户即使离开了 AI 测试页，也能回到历史成功记录继续沉淀用例。

---

## 12. 没有快照 / 老记录的处理

这部分采用最保守策略。

### 12.1 无 `ui_flow_snapshot`

无论原因是：

- 旧版本历史记录；
- 异常数据；
- 迁移前执行记录；

只要没有 `ui_flow_snapshot`，就：

- 前端按钮禁用；
- 后端接口拒绝；
- 提示“该执行记录未保存可复用流程，请重新执行成功后再保存”。

### 12.2 不做历史回填

V1 不做：

- 日志解析回填；
- `planned_tasks` 反推 `ui_flow`；
- 批量迁移旧记录。

原因很简单：

> **比起“兼容旧记录”，更重要的是“新保存出来的用例 100% 可执行”。**

---

## 13. 测试策略

### 13.1 后端单测

至少覆盖以下场景：

1. `run_mobile_execution()` 成功生成后会保存 `ui_flow_snapshot`；
2. `AIExecutionRecordSerializer` 能正确返回：
   - `saved_app_test_case`
   - `saved_app_test_case_name`
   - `can_save_as_app_test_case`
3. 成功移动端记录可保存为 `AppTestCase`；
4. 失败记录不可保存；
5. 无 `ui_flow_snapshot` 的记录不可保存；
6. 同一记录重复保存不会创建第二条 `AppTestCase`；
7. `if` 等嵌套步骤在清洗后结构保持可执行。

### 13.2 前端验证

至少验证：

1. `保存为 AI 模板` 仍可正常使用；
2. `保存为 APP 测试用例` 只在成功记录上可点；
3. 保存成功后能跳转到 `/app-automation/test-cases`；
4. 历史记录页入口与禁用态文案正确。

---

## 14. 风险与控制

### 风险 1：`ui_flow` DSL 后续扩展

如果未来 `UiFlowRunner` 支持更多字段，清洗白名单可能遗漏。

**控制方式**
- 把清洗逻辑集中成单独 helper；
- 为新增 DSL 字段补单测；
- 让清洗策略显式演进，而不是直接整包透传。

### 风险 2：用户误以为“保存的是输入框文本”

**控制方式**
- 文案明确区分“AI 模板”和“APP 测试用例”；
- APP 测试用例保存入口严格绑定执行记录；
- 仅成功后开放。

### 风险 3：用户担心未绑定 `app_package` 会不会跑不起来

**控制方式**
- 在说明文案中强调：启动包信息已经在 `ui_flow.start_app.package_name` 中；
- 执行入口仍然要求用户重新选择设备。

---

## 15. 最终结论

这次设计的关键结论是：

1. **必须新增 `AIExecutionRecord.ui_flow_snapshot`，并在移动端执行时写入真实流程快照。**
2. **保存为 APP 测试用例必须只针对成功记录开放。**
3. **保存动作必须直接创建 `AppTestCase`，而不是保存自然语言模板。**
4. **没有快照的旧记录一律不做反推回填，提示重新执行。**

按照这套方案落地后，用户将得到一条真正闭环的路径：

> **自然语言描述 → AI 真机跑通 → 一键固化成标准 APP 测试用例 → 后续直接复用。**
