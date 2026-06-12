# Android Stability Check Defaults Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 APP 自动化项目在创建时自动生成默认稳定性套件与默认随机点击用例，并把崩溃/ANR/退后台等异常的日志证据落地到执行记录中可查看、可下载。

**Architecture:** 在 `AppProject` 增加项目级默认包名，在 `AppTestExecution` 增加稳定性失败类型与产物元数据。项目创建后通过幂等初始化逻辑自动生成 `Android Stability Check` 套件和 `随机点击稳定性检查` 用例；执行链统一按“运行时覆盖 > 定时任务包名 > 用例包名 > 项目默认包名”解析目标包名；`UiFlowRunner` 新增 `RANDOM_TAP_STRESS` 动作并将异常证据写入固定产物目录，执行器与执行记录 API 负责回填、展示与下载。

**Tech Stack:** Django ORM / DRF、Celery、pytest、Airtest + ADB、Vue 3 + Element Plus、YAML component pack。

---

### Task 1: 扩展项目与执行记录数据模型
**Files:**
- Modify: `apps/app_automation/constants.py`
- Modify: `apps/app_automation/models.py`
- Modify: `apps/app_automation/serializers.py`
- Create: `apps/app_automation/migrations/0003_project_defaults_and_execution_artifacts.py`
- Test: `apps/app_automation/tests/test_project_execution_serializers.py`

**Step 1: Write the failing test**
- 断言 `AppProjectSerializer` 能读写 `default_app_package`，并能返回 `default_app_package_name` 与 `default_app_package_package_name`。
- 断言 `AppTestExecutionSerializer` 会输出 `failure_type`、`runtime_summary`、`artifacts`。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_project_execution_serializers.py -v`
- Expected: FAIL，提示序列化字段或模型字段不存在。

**Step 3: Write minimal implementation**
- 在 `AppProject` 增加 `default_app_package = models.ForeignKey(AppPackage, null=True, blank=True, on_delete=models.SET_NULL, related_name='default_for_projects')`。
- 在 `constants.py` 增加稳定性失败类型常量：`CRASH`、`ANR`、`BACKGROUND`、`DEVICE_DISCONNECTED`、`UNKNOWN`。
- 在 `AppTestExecution` 增加：
  - `failure_type = models.CharField(max_length=32, blank=True, default='')`
  - `runtime_summary = models.JSONField(default=dict, blank=True)`
  - `artifacts = models.JSONField(default=list, blank=True)`
- 更新项目/执行记录 serializer，把上述字段暴露给前端。
- 生成迁移文件 `0003_project_defaults_and_execution_artifacts.py`。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_project_execution_serializers.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/constants.py apps/app_automation/models.py apps/app_automation/serializers.py apps/app_automation/migrations/0003_project_defaults_and_execution_artifacts.py apps/app_automation/tests/test_project_execution_serializers.py`
- `git commit -m "feat: add project default package and execution artifact metadata"`

### Task 2: 项目创建时幂等生成默认稳定性套件
**Files:**
- Create: `apps/app_automation/project_bootstrap.py`
- Modify: `apps/app_automation/views/project_views.py`
- Test: `apps/app_automation/tests/test_project_bootstrap.py`

**Step 1: Write the failing test**
- 通过项目创建接口创建新项目后，断言自动生成：
  - 套件 `Android Stability Check`
  - 用例 `随机点击稳定性检查`
  - 套件/用例关联关系 `AppTestSuiteCase`
- 断言默认用例的 `app_package` 继承 `project.default_app_package`。
- 断言重复调用初始化函数不会重复创建同名默认套件。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_project_bootstrap.py -v`
- Expected: FAIL，提示没有生成默认套件/用例或发生重复创建。

**Step 3: Write minimal implementation**
- 在 `project_bootstrap.py` 实现 `bootstrap_default_stability_suite(project, created_by)`：
  - 幂等查找同项目下的 `Android Stability Check`
  - 若不存在则创建套件与默认用例
  - 默认用例 `ui_flow` 只包含一个 `RANDOM_TAP_STRESS` 步骤
  - 默认步骤配置包含：`duration_seconds`、`tap_interval_ms`、`safe_margin`、`foreground_grace_seconds`、`relaunch_on_background`、`collect_logcat`、`collect_screenshot`、`exclude_regions`
- 在 `AppProjectViewSet.perform_create()` 中，`serializer.save(owner=...)` 后调用 bootstrap helper。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_project_bootstrap.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/project_bootstrap.py apps/app_automation/views/project_views.py apps/app_automation/tests/test_project_bootstrap.py`
- `git commit -m "feat: bootstrap default android stability suite on project creation"`

### Task 3: 统一单用例、套件、定时任务三条链的包名解析
**Files:**
- Create: `apps/app_automation/package_resolution.py`
- Modify: `apps/app_automation/views/test_case_views.py`
- Modify: `apps/app_automation/views/suite_views.py`
- Modify: `apps/app_automation/views/scheduled_task_views.py`
- Modify: `apps/app_automation/tasks.py`
- Test: `apps/app_automation/tests/test_package_resolution.py`

**Step 1: Write the failing test**
- 为 helper 写优先级测试，断言解析规则为：
  1. 显式 `package_name` 覆盖
  2. 定时任务 `task.app_package`
  3. 用例 `test_case.app_package`
  4. 项目 `test_case.project.default_app_package`
  5. 空字符串
- 为单用例执行、套件执行、定时任务执行分别写测试，断言三条链都调用同一套解析逻辑。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_package_resolution.py -v`
- Expected: FAIL，当前逻辑不会回退到项目默认包名，且三条链行为不一致。

**Step 3: Write minimal implementation**
- 在 `package_resolution.py` 中实现：
  - `resolve_test_case_package_name(test_case, override_package_name=None)`
  - `resolve_scheduled_package_name(task, test_case=None, override_package_name=None)`
- 在 `test_case_views.py`、`suite_views.py`、`scheduled_task_views.py`、`tasks.py` 中统一调用 helper，而不是各自拼接 `if package_name else test_case.app_package...`。
- 保持 API 兼容：前端仍可传 `package_name` 覆盖；不传时自动兜底到项目默认包名。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_package_resolution.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/package_resolution.py apps/app_automation/views/test_case_views.py apps/app_automation/views/suite_views.py apps/app_automation/views/scheduled_task_views.py apps/app_automation/tasks.py apps/app_automation/tests/test_package_resolution.py`
- `git commit -m "feat: unify app package resolution across execution entrypoints"`

### Task 4: 为 UiFlowRunner 增加 RANDOM_TAP_STRESS 与稳定性证据采集
**Files:**
- Create: `apps/app_automation/utils/android_stability.py`
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_random_tap_stress.py`

**Step 1: Write the failing test**
- 断言 `RANDOM_TAP_STRESS` 在步骤未传 `package_name` 时优先读取运行时目标包名。
- 断言当前台包名丢失并超过 `foreground_grace_seconds` 时抛出稳定性失败异常。
- 断言 `safe_margin` 会限制点击坐标不落在屏幕边缘。
- 断言异常发生时会写出 `summary.json`，并记录 `logcat.txt`、`activity.txt`、`anr.txt`、`crash.png` 等产物元数据。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_random_tap_stress.py -v`
- Expected: FAIL，当前 runner 不认识 `random_tap_stress`，也不会写稳定性产物。

**Step 3: Write minimal implementation**
- 在 `android_stability.py` 中实现：
  - 前台包名检测
  - 设备在线检测
  - ANR/崩溃诊断命令采集
  - 随机点击坐标生成
  - 产物目录写入（固定写到 `media/app-automation/executions/execution_<id>/`）
- 在 `UiFlowRunner._dispatch_step()` 的 `action_map` 中注册 `random_tap_stress`。
- 新增 `_action_random_tap_stress()`：
  - 读取运行时 `app_package_name` / `artifact_dir` / `execution_id`
  - 循环随机点击直到超时或异常
  - 对崩溃、ANR、退后台、设备断连统一写 `summary.json`
  - `relaunch_on_background=true` 时允许短暂拉回，否则直接判失败

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_ui_flow_runner_random_tap_stress.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/utils/android_stability.py apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_random_tap_stress.py`
- `git commit -m "feat: add random tap stability stress action"`

### Task 5: 让 pytest 执行器回填稳定性摘要与产物元数据
**Files:**
- Modify: `apps/app_automation/executors/test_executor.py`
- Modify: `apps/app_automation/tasks.py`
- Modify: `apps/app_automation/tests/test_app_flow.py`
- Modify: `apps/app_automation/tests/test_app_executor.py`
- Create: `apps/app_automation/tests/test_execution_artifact_backfill.py`

**Step 1: Write the failing test**
- 断言 `AppTestExecutor.run_tests()` 会为每次执行创建独立产物目录，并把目录路径传给 pytest 子进程。
- 断言当产物目录下存在 `summary.json` 时，`run_tests()` 返回值会包含 `failure_type`、`runtime_summary`、`artifacts`。
- 断言 `execute_app_test_task()` 与 `execute_app_suite_task()` 会把这些字段回填到 `AppTestExecution`。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_app_executor.py apps/app_automation/tests/test_execution_artifact_backfill.py -v`
- Expected: FAIL，当前执行器只回传 Allure 与 step 统计，不处理稳定性产物。

**Step 3: Write minimal implementation**
- 在 `AppTestExecutor.run_tests()` 中：
  - 创建 `media/app-automation/executions/execution_<id>/`
  - 注入 `APP_EXECUTION_ARTIFACT_DIR` 环境变量
  - pytest 结束后扫描 `summary.json`，构造相对路径产物列表
- 在 `test_app_flow.py` 中，把 `package_name`、`execution_id`、`artifact_dir` 放入 `UiFlowRunner.run(runtime=...)`。
- 在 `tasks.py` 中对 case/suite 两条执行链统一回填：
  - `failure_type`
  - `runtime_summary`
  - `artifacts`
  - 必要时将失败原因追加到 `error_message`

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_app_executor.py apps/app_automation/tests/test_execution_artifact_backfill.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/executors/test_executor.py apps/app_automation/tasks.py apps/app_automation/tests/test_app_flow.py apps/app_automation/tests/test_app_executor.py apps/app_automation/tests/test_execution_artifact_backfill.py`
- `git commit -m "feat: persist stability artifacts into app test executions"`

### Task 6: 为执行记录提供稳定性产物详情与下载接口
**Files:**
- Modify: `apps/app_automation/views/execution_views.py`
- Modify: `apps/app_automation/urls.py`
- Test: `apps/app_automation/tests/test_execution_views.py`

**Step 1: Write the failing test**
- 断言执行记录详情接口能返回 `failure_type`、`runtime_summary`、`artifacts`。
- 断言新增的产物文件接口可以下载 `media/app-automation/executions/execution_<id>/` 下的文件。
- 断言路径穿越（例如 `../../settings.py`）会被 404 拒绝。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/app_automation/tests/test_execution_views.py -v`
- Expected: FAIL，当前只有 Allure 报告文件服务，没有稳定性产物访问入口。

**Step 3: Write minimal implementation**
- 在 `execution_views.py` 新增 `serve_execution_artifact_file()`，路径安全校验逻辑复用报告服务的做法。
- 在 `urls.py` 增加：
  - `path('executions/<int:execution_id>/artifacts/<path:file_path>', ...)`
- 若 `artifacts` 中只存相对路径，则在 serializer 或 view 层补 `download_url`，前端无需自己拼目录。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/app_automation/tests/test_execution_views.py -v`
- Expected: PASS

**Step 5: Commit**
- `git add apps/app_automation/views/execution_views.py apps/app_automation/urls.py apps/app_automation/tests/test_execution_views.py`
- `git commit -m "feat: expose execution artifact download endpoints"`

### Task 7: 更新基础组件包并让场景编辑器识别新步骤配置
**Files:**
- Modify: `apps/core/management/commands/ui-component-pack.yaml`
- Create: `apps/core/tests/__init__.py`
- Create: `apps/core/tests/test_load_component_pack.py`
- Modify: `frontend/src/views/app-automation/test-cases/SceneBuilder.vue`

**Step 1: Write the failing test**
- 后端：写 `load_component_pack` 回归测试，断言导入后存在 `RANDOM_TAP_STRESS` 组件，且 `default_config` 含 `duration_seconds`、`tap_interval_ms`、`safe_margin`、`exclude_regions`、`relaunch_on_background`、`foreground_grace_seconds`。
- 前端：如果没有 UI 单测框架，先以静态检查为准，确认 `SceneBuilder.vue` 里已有标签/placeholder/数字规则还不包含这些新字段。

**Step 2: Run test to verify it fails**
- Run: `pytest apps/core/tests/test_load_component_pack.py -v`
- Run: `cd frontend && npm run lint -- src/views/app-automation/test-cases/SceneBuilder.vue`
- Expected: pytest FAIL（缺少组件定义）；lint PASS 或 FAIL 都可以，但页面仍无法友好展示这些字段。

**Step 3: Write minimal implementation**
- 在 `ui-component-pack.yaml` 增加组件定义：
  - `type: RANDOM_TAP_STRESS`
  - `category: action`
  - 详细 `schema.required` 与 `schema.properties`
  - 对应 `default_config`
- 在 `SceneBuilder.vue` 增加：
  - 新字段中文标签
  - placeholder 文案
  - 数值步进规则
  - 布尔/枚举字段展示映射（如 `relaunch_on_background`）
- 保持 generic schema 渲染机制，不为单个步骤硬编码独立面板。

**Step 4: Run test to verify it passes**
- Run: `pytest apps/core/tests/test_load_component_pack.py -v`
- Run: `cd frontend && npm run lint -- src/views/app-automation/test-cases/SceneBuilder.vue`
- Expected: PASS

**Step 5: Commit**
- `git add apps/core/management/commands/ui-component-pack.yaml apps/core/tests/__init__.py apps/core/tests/test_load_component_pack.py frontend/src/views/app-automation/test-cases/SceneBuilder.vue`
- `git commit -m "feat: add random tap stress component definition"`

### Task 8: 在项目页与执行页接入默认包名和稳定性产物展示
**Files:**
- Modify: `frontend/src/views/app-automation/projects/ProjectList.vue`
- Modify: `frontend/src/views/app-automation/executions/ExecutionList.vue`
- Modify: `frontend/src/api/app-automation.js`

**Step 1: Write the failing test**
- 如果没有前端单测框架，则先写静态验收清单：
  - 项目创建/编辑弹窗必须可选择 `default_app_package`
  - 项目详情弹窗必须显示默认包名
  - 执行记录列表必须能打开“稳定性详情/产物”弹窗
  - 详情中必须显示 `failure_type`、摘要字段、下载链接

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run lint -- src/views/app-automation/projects/ProjectList.vue src/views/app-automation/executions/ExecutionList.vue src/api/app-automation.js`
- Expected: lint PASS 或 FAIL 都可以，但当前页面不具备默认包名选择与稳定性详情展示能力。

**Step 3: Write minimal implementation**
- 在 `ProjectList.vue`：
  - 复用 `getPackageList({ page_size: 100 })`
  - 新增项目表单 `default_app_package`
  - 在详情区展示包名名称与实际 `package_name`
- 在 `ExecutionList.vue`：
  - 按需调用 `getExecutionDetail(id)`
  - 新增详情弹窗，展示 `failure_type`、`runtime_summary`
  - 对 `artifacts` 渲染下载链接，图片类产物可增加预览
  - 保留现有查看 Allure 报告/错误信息按钮
- 在 `app-automation.js` 中按需补充产物 URL helper 或保持现有 `getExecutionDetail()` 复用。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run lint -- src/views/app-automation/projects/ProjectList.vue src/views/app-automation/executions/ExecutionList.vue src/api/app-automation.js`
- Expected: PASS

**Step 5: Commit**
- `git add frontend/src/views/app-automation/projects/ProjectList.vue frontend/src/views/app-automation/executions/ExecutionList.vue frontend/src/api/app-automation.js`
- `git commit -m "feat: surface project default package and stability artifacts in ui"`

### Task 9: 全链路验证与收尾
**Files:**
- Modify: `docs/plans/2026-06-12-android-stability-check.md`

**Step 1: Run backend targeted tests**
- Run: `pytest apps/app_automation/tests/test_project_execution_serializers.py apps/app_automation/tests/test_project_bootstrap.py apps/app_automation/tests/test_package_resolution.py apps/app_automation/tests/test_ui_flow_runner_random_tap_stress.py apps/app_automation/tests/test_app_executor.py apps/app_automation/tests/test_execution_artifact_backfill.py apps/app_automation/tests/test_execution_views.py apps/core/tests/test_load_component_pack.py -v`
- Expected: 全部 PASS

**Step 2: Reload the component pack into the database**
- Run: `python manage.py load_component_pack --overwrite`
- Expected: 输出中包含 `RANDOM_TAP_STRESS` 的 `[OK]` 或 `[UPDATE]` 记录。

**Step 3: Run frontend checks**
- Run: `cd frontend && npm run lint -- src/views/app-automation/projects/ProjectList.vue src/views/app-automation/test-cases/SceneBuilder.vue src/views/app-automation/executions/ExecutionList.vue src/api/app-automation.js`
- Run: `cd frontend && npm run build`
- Expected: PASS

**Step 4: Manual smoke test**
- 新建一个带默认包名的 APP 项目。
- 确认自动生成 `Android Stability Check` 套件和 `随机点击稳定性检查` 用例。
- 在场景编辑器打开默认用例，确认 `RANDOM_TAP_STRESS` 字段可编辑。
- 绑定设备手动执行一次；若刻意制造退后台/崩溃/ANR，确认执行记录中能看到失败类型、摘要和日志/截图下载链接。
- 创建一个 `TEST_SUITE` 类型定时任务，确认未显式传包名时仍能跑到项目默认包名。

**Step 5: Commit**
- `git add apps/app_automation apps/core frontend docs/plans/2026-06-12-android-stability-check.md`
- `git commit -m "feat: add default android stability suite and crash artifact pipeline"`
