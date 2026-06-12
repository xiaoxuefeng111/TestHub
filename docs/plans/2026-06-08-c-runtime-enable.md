# 通达信测试平台 C 档可用状态 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让通达信测试平台在当前 Windows 开发机达到 C 档可用状态：前后端可启动，SQLite 本地可用，Redis/Celery/WebSocket 可工作，UI 自动化与 APP 自动化关键依赖可用，Allure 报告链路可生成。

**Architecture:** 先修复并对齐本地 Python/Node 运行时，再补齐 Redis、Playwright/Selenium、Airtest/OCR、Java/Allure 等增强依赖，最后以真实启动与关键页面/任务链路验证收口。优先使用仓库现有 `.venv`、`.env`、`allure/` 和前端现成依赖，避免无谓改代码；仅在环境补齐后仍有阻塞时才做最小代码修正。

**Tech Stack:** Django 4.2, Vue 3 + Vite, SQLite, Redis, Celery, Channels, Playwright, Selenium, Airtest, EasyOCR, Allure, Java 17, ADB.

---

### Task 1: 冻结当前基线并确认验收口径

**Files:**
- Modify: `docs/plans/2026-06-08-c-runtime-enable.md`
- Review: `.env`
- Review: `requirements.txt`
- Review: `backend/settings.py`
- Review: `frontend/package.json`

**Step 1: 记录当前环境现状**

Run: `py -V`, `.venv\Scripts\python.exe -V`, `node -v`, `npm -v`, `adb version`
Expected: 形成当前 Python/Node/ADB 基线。

**Step 2: 记录当前缺口**

Run: `.venv\Scripts\pip.exe show django celery redis channels daphne playwright selenium airtest easyocr`
Expected: 确认 Django 版本漂移和增强依赖缺失情况。

**Step 3: 记录当前可通过项**

Run: `.venv\Scripts\python.exe manage.py check`, `cd frontend && npm run build`
Expected: 后端基础检查可过，前端 build 可过。

**Step 4: 验收口径固定**

Expected:
- 后端 HTTP 可启动
- 前端 dev 可启动
- Redis 可连接
- Celery worker 可启动
- WebSocket 链路可建立
- Playwright / Selenium 可执行基础检查
- Airtest / OCR / Allure 依赖可导入或生成结果

**Step 5: Commit**

不提交，仅更新计划文档。

### Task 2: 修复 Python 虚拟环境并对齐后端依赖

**Files:**
- Review: `requirements.txt`
- Review: `CLAUDE.md`
- Optional Modify: `.env`

**Step 1: 使用现有 `.venv` 对齐 requirements**

Run: `.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel`
Expected: pip 基础工具更新完成。

**Step 2: 安装仓库 Python 依赖**

Run: `.venv\Scripts\python.exe -m pip install -r requirements.txt`
Expected: Django 降回 4.2.7，并补齐 daphne / playwright / selenium / airtest / easyocr 等依赖。

**Step 3: 验证关键依赖版本**

Run: `.venv\Scripts\pip.exe show django daphne playwright selenium airtest easyocr channels-redis`
Expected: 版本与项目约束一致，或至少兼容。

**Step 4: 再次运行 Django 自检**

Run: `.venv\Scripts\python.exe manage.py check`
Expected: 无导入级报错。

**Step 5: Commit**

不提交，先继续验证运行时。

### Task 3: 校准数据库与 Django 基础数据

**Files:**
- Review/Modify: `.env`
- Review: `backend/settings.py`
- Review: `apps/core/management/commands/init_locator_strategies.py`

**Step 1: 固定本地数据库策略**

Check: `.env` 中 `USE_SQLITE=True`
Expected: 本地不依赖 MySQL。

**Step 2: 执行迁移**

Run: `.venv\Scripts\python.exe manage.py migrate`
Expected: SQLite schema 与代码对齐。

**Step 3: 初始化 UI 自动化基础数据**

Run: `.venv\Scripts\python.exe manage.py init_locator_strategies`
Expected: 页面元素定位策略初始化成功。

**Step 4: 抽查关键模型/API 是否可加载**

Run: `.venv\Scripts\python.exe manage.py shell -c "from apps.projects.models import Project; print(Project.objects.count())"`
Expected: ORM 可正常访问 SQLite。

**Step 5: Commit**

不提交，继续服务层验证。

### Task 4: 补齐 Redis / Celery / Channels 运行时

**Files:**
- Review/Modify: `.env`
- Review: `backend/settings.py`
- Review: `backend/asgi.py`
- Review: `backend/celery.py`
- Review: `apps/app_automation/apps.py`

**Step 1: 准备 Redis 服务**

Run: `winget search redis`
Expected: 找到可安装的 Windows Redis 发行版（如 Memurai/Redis for Windows）。

**Step 2: 安装并启动 Redis**

Run: 依据搜索结果执行安装与启动命令。
Expected: `127.0.0.1:6379` 可连接。

**Step 3: 验证 Django 对 Redis 的连接**

Run: `.venv\Scripts\python.exe manage.py shell -c "from django.conf import settings; print(settings.REDIS_URL)"`
Expected: REDIS_URL 指向本机 Redis。

**Step 4: 验证 Celery worker**

Run: `.venv\Scripts\celery.exe -A backend worker -l info --pool=solo`
Expected: worker 成功启动并连接 broker。

**Step 5: 验证 ASGI / Channels**

Run: `.venv\Scripts\python.exe -c "import backend.asgi; print('asgi ok')"`
Expected: WebSocket 路由可导入。

### Task 5: 补齐 Web UI 自动化工具链

**Files:**
- Review: `apps/ui_automation/views_config.py`
- Review: `apps/core/management/commands/download_webdrivers.py`
- Review: `apps/ui_automation/test_executor.py`

**Step 1: 安装 Python Playwright 运行时**

Run: `.venv\Scripts\python.exe -m playwright install chromium firefox webkit`
Expected: Playwright 浏览器缓存安装完成。

**Step 2: 下载 Selenium 驱动**

Run: `.venv\Scripts\python.exe manage.py download_webdrivers`
Expected: 浏览器驱动可下载或生成。

**Step 3: 验证 Playwright 导入**

Run: `.venv\Scripts\python.exe -c "from playwright.sync_api import sync_playwright; print('playwright ok')"`
Expected: Python Playwright 可导入。

**Step 4: 验证 Selenium 导入**

Run: `.venv\Scripts\python.exe -c "from selenium import webdriver; print('selenium ok')"`
Expected: Selenium 可导入。

**Step 5: Commit**

不提交，继续 APP 自动化依赖。

### Task 6: 补齐 APP 自动化工具链

**Files:**
- Review: `apps/app_automation/utils/airtest_base.py`
- Review: `apps/app_automation/utils/ocr_helper.py`
- Review: `apps/app_automation/runners/ui_flow_runner.py`

**Step 1: 验证 Airtest/OCR 依赖**

Run: `.venv\Scripts\python.exe -c "import airtest, easyocr, cv2; print('airtest/ocr ok')"`
Expected: 核心 APP 自动化依赖可导入。

**Step 2: 验证 ADB 可用**

Run: `adb devices`
Expected: ADB 正常响应（可无设备，但命令需可用）。

**Step 3: 抽查 APP 自动化模块导入**

Run: `.venv\Scripts\python.exe -c "from apps.app_automation.runners.ui_flow_runner import UiFlowRunner; print('app runner ok')"`
Expected: APP 执行核心模块可导入。

**Step 4: 若导入失败，做最小兼容修复**

Modify if needed:
- `apps/app_automation/*`
- `backend/settings.py`
Expected: 不因非关键可选依赖在导入期直接崩溃。

**Step 5: Commit**

仅在确有代码修复时准备提交。

### Task 7: 打通 Allure 报告链路

**Files:**
- Review: `apps/api_testing/views.py`
- Review: `apps/app_automation/executors/test_executor.py`
- Review: `allure/bin/allure.bat`

**Step 1: 验证 Java 运行时**

Run: `"C:\Program Files\Java\jdk-17.0.10\bin\java.exe" -version`
Expected: Java 17 可运行。

**Step 2: 验证项目内置 Allure**

Run: `allure\bin\allure.bat --version`
Expected: Allure CLI 可执行。

**Step 3: 生成一次最小报告烟测**

Run: 使用临时结果目录执行 `allure generate`。
Expected: 报告目录可生成。

**Step 4: 若 PATH/JAVA_HOME 缺失，则补充本地启动脚本或文档**

Modify if needed:
- `.env`
- `docs/*`
Expected: 后续同机启动不再受 Java 路径影响。

### Task 8: 端到端启动与关键链路验证

**Files:**
- Review: `frontend/src/router/index.js`
- Review: `frontend/src/views/Home.vue`
- Optional Modify: `backend/settings.py`
- Optional Modify: `.env`

**Step 1: 启动 Django HTTP 服务**

Run: `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
Expected: HTTP API 可访问。

**Step 2: 启动前端开发服务**

Run: `cd frontend && npm run dev`
Expected: 前端代理到 8000 正常。

**Step 3: 启动 Celery worker**

Run: `.venv\Scripts\celery.exe -A backend worker -l info --pool=solo`
Expected: 后台任务链路可用。

**Step 4: 使用页面烟测验证**

Check pages:
- `/home`
- `/api-testing/interfaces`
- `/ui-automation/elements-enhanced`
- `/app-automation/dashboard`
- `/ai-generation/requirement-analysis`
Expected: 基础页可进，增强页不再因依赖缺失首屏即崩。

**Step 5: 若页面失败，定位为配置问题还是代码问题并最小修正**

Modify if needed:
- `backend/settings.py`
- `frontend/src/utils/api.js`
- 具体报错所在模块
Expected: 收敛剩余阻塞项。

---

Plan complete and saved to `docs/plans/2026-06-08-c-runtime-enable.md`.

默认执行方式：**当前会话继续推进**（你已经明确选择 C 档）。如果你想切换成“新会话按计划并行执行”，我也可以改用单独执行流。