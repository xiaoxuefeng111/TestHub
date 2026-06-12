# 通达信测试平台本地开发运行说明（Windows）

> 这份 README 同时覆盖 **项目能力概览** 与 **Windows 本地开发最小可运行链路**：`SQLite + Django + Vite`。
> 
> 当前版本重点增强 **AI 智能测试**，尤其是 **手机端自然语言驱动的自主执行能力**；本地开发默认仍 **优先使用 SQLite**，不再把 MySQL 作为默认前置条件。

## 0. 项目简介

通达信测试平台是一个面向测试团队的智能测试管理平台，覆盖测试用例管理、接口测试、Web/UI 自动化、APP 自动化、执行记录、测试报告与 AI 辅助测试能力。

本次 README 重点补充的平台能力是：**AI 智能测试已从传统 Web 文本任务扩展到手机端场景**，支持面向 Android 真机/设备，通过自然语言描述测试目标，由系统自动生成可执行步骤并完成移动端 UI 测试。

## 0.1 本次重点改造：AI 智能测试（手机端）

当前 AI 智能测试的重点能力包括：

- **支持手机端 AI 自主执行**：新增 `execution_mode=mobile` 执行模式，面向移动设备执行 AI 测试任务。
- **支持自然语言驱动**：用户可以直接输入自然语言步骤，例如登录、切换页面、输入账号、点击按钮、等待页面结果、截图留证等。
- **支持自然语言解析为结构化执行计划**：系统会优先通过规则语义解析器将用户描述转换为受限 DSL；当规则解析不适用时，再回退到 LLM 规划生成移动端 UI Flow。
- **支持真实设备与目标应用绑定**：移动端执行记录会关联目标设备（`app_device`）与目标应用包（`app_package`），便于追踪执行上下文。
- **支持 OCR 驱动的页面理解与操作**：执行过程围绕页面文字识别进行等待、点击、输入、滑动查找与结果断言，减少对固定坐标和模板图的依赖。
- **支持执行过程留痕**：执行日志、执行模式、设备信息、应用信息、截图等都会沉淀到 AI 执行记录中，便于回放与问题分析。
- **支持任务沉淀与复用**：完成验证的自然语言任务可以进一步沉淀为可复用用例，结合 AI 执行记录形成“描述—执行—复盘—复用”的闭环，降低移动端回归测试的重复编排成本。

## 0.2 手机端 AI 智能测试执行链路

移动端 AI 智能测试的核心链路如下：

1. **用户输入自然语言任务**  
   例如：
   - 打开通达信 APP
   - 点击“交易”
   - 如果账号为空就输入 `123456`，否则直接聚焦密码框
   - 输入密码 `888888`
   - 点击“登录”
   - 等待首页出现并截图

2. **语义解析与计划校验**  
   系统优先使用 `MobileSemanticParser` 将自然语言解析为受限 DSL，再由 `MobilePlanValidator` 校验关键字面值、点击目标与步骤完整性。

3. **生成移动端 UI Flow**  
   解析成功时走确定性结构化流程；复杂场景下由 `MobileFlowPlanner` 调用大模型补充规划，最终统一编译为移动端可执行步骤。

4. **真机执行**  
   执行引擎通过 `AirtestBase + ADB + UiFlowRunner` 驱动 Android 设备，对目标应用执行启动、等待文本、点击文本、输入、滑动查找、按键、断言和截图等动作。

5. **结果留存与问题分析**  
   系统会保存 AI 执行记录、执行日志、目标设备/应用信息、执行模式与截图结果，便于后续排查与优化自然语言测试指令；经过验证的任务描述还可以继续沉淀为标准化测试资产，用于后续复用与回归执行。

## 0.3 当前移动端 AI 已支持的典型动作

当前移动端自然语言执行链路已重点覆盖以下高频场景：

- 启动指定 APP
- 等待页面文字出现
- 点击页面文字
- 聚焦输入框并输入文本
- 滑动直到目标文字出现
- 发送系统按键（如返回）
- 断言结果文字可见
- 执行结束截图
- 基于字段是否为空的简单条件分支

这类能力适合覆盖登录、搜索、菜单切换、表单填写、结果校验等移动端高频回归场景。

## 0.4 相关技术栈

### 平台基础技术栈

- **Backend**：Django 4.2、Django REST Framework、drf-spectacular
- **Frontend**：Vue 3、Vite、Element Plus、Pinia、Vue Router、Vue I18n
- **异步与实时能力**：Celery、Redis、Channels、Daphne
- **数据库**：SQLite（本地开发默认）、MySQL（生产/正式环境可接入）

### AI 智能测试技术栈

- **LLM 编排**：LangChain、`langchain-openai`、OpenAI 兼容模型接入
- **移动端语义理解**：`MobileSemanticParser`、`MobilePlanValidator`、`MobileFlowPlanner`
- **移动端执行引擎**：`UiFlowRunner`、`AirtestBase`
- **设备连接与控制**：ADB（Android Debug Bridge）
- **页面理解与识别**：EasyOCR、OpenCV、Pillow
- **Web 自动化能力**：Playwright、Selenium
- **测试资产沉淀**：自然语言任务描述、AI 执行记录与标准化测试用例管理能力可组合使用，支撑移动端测试资产复用与持续回归

### 当前手机端 AI 方案的关键特点

- **优先规则解析，降低幻觉风险**：能用规则语义解析的场景，优先走确定性 DSL，而不是直接把所有任务都交给大模型自由发挥。
- **以文字识别驱动 UI 操作**：重点围绕 OCR 文本进行等待、点击与断言，更适合复杂但结构不稳定的移动端页面。
- **保留大模型兜底能力**：当规则解析无法完整覆盖任务时，可回退到大模型规划，兼顾稳定性与泛化能力。

## 当前已知可运行事实

以下事实来自当前协作上下文，已可作为本地开发基线：

- `.venv\Scripts\python.exe manage.py check` 已通过
- 数据库迁移可复现，`makemigrations --check --dry-run` 在默认配置与 `ANALYTICS_ENABLED=true` 下都通过
- Django 后端可在 `127.0.0.1:8000` 启动
- `http://127.0.0.1:8000/api/schema/` 返回 `200`
- `http://127.0.0.1:8000/api/docs/` 返回 `200`
- `npm --prefix frontend run build` 已通过
- Vite 前端可在 `127.0.0.1:3000` 启动
- `http://127.0.0.1:3000/home` 停留在 `/home`
- 页面显示已登录用户 `local-dev`
- 浏览器控制台无错误

---

## 1. 环境要求

推荐在 Windows 10/11 + PowerShell 下运行。

- Python `3.12`
- Node.js `20.19+`（或 `22.12+`）
- npm `9+`

本地最小启动 **不要求**：

- MySQL
- Redis
- Celery Worker
- Java / Allure
- 浏览器驱动
- AI / 短信 / 邮件配置

这些能力属于扩展功能，不影响最小开发链路。

---

## 2. 仓库初始化

如果你还没有拉代码：

```powershell
git clone <repository-url>
cd testhub_platform
```

如果仓库里已经有 `.venv`，可以直接复用；没有再创建。

### 2.1 创建虚拟环境

```powershell
py -3.12 -m venv .venv
```

### 2.2 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻止执行脚本：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

后续示例里的 Python 命令更推荐直接写 `.venv\Scripts\python.exe`，这样即使忘了激活环境，也不会混用系统 Python。

### 2.3 安装后端依赖

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2.4 安装前端依赖

```powershell
npm --prefix frontend install
```

---

## 3. 配置 `.env`

从模板复制：

```powershell
Copy-Item .env.example .env
```

本地最小启动至少确认这些值：

```env
SECRET_KEY=change-me-for-local-dev
DEBUG=True
USE_SQLITE=True
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

如果你要走当前已验证的前后端联调最小路径，再额外确认：

```env
DEV_LOGIN_ENABLED=True
VITE_LOCAL_DEV_AUTH=true
```

说明：

- `USE_SQLITE=True` 是当前推荐的本地开发模式
- `frontend/vite.config.js` 已把 `/api` 代理到 `http://127.0.0.1:8000`
- `.env.example` 中用于本地开发自动登录的真实键名应与代码保持一致：`DEV_LOGIN_ENABLED`、`VITE_LOCAL_DEV_AUTH`
- 本地开发默认 **不需要** 填 MySQL、Redis、短信、邮件等配置

---

## 4. 初始化 SQLite 数据库

首次启动或本地数据库需要重建时执行：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

首次启动先执行 `migrate`；不要把 `makemigrations` 当作入门步骤。`makemigrations --check --dry-run` 更适合在你修改 model 后做迁移一致性校验。

如果你需要进入 Django Admin，再额外创建管理员账号：

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

SQLite 文件默认位于仓库根目录：

```text
db.sqlite3
```

---

## 5. 启动后端

在仓库根目录执行（推荐直接使用 `.venv\Scripts\python.exe`，避免混用系统 Python）：

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

启动成功后，优先验证：

- Schema：`http://127.0.0.1:8000/api/schema/`
- Swagger：`http://127.0.0.1:8000/api/docs/`
- Admin（可选）：`http://127.0.0.1:8000/admin/`

---

## 6. 启动前端

另开一个 PowerShell 窗口，进入 `frontend` 目录执行：

```powershell
cd frontend
npm run dev
```

推荐联调访问地址：

- `http://127.0.0.1:3000/home`

说明：

- Vite 当前实际监听 `127.0.0.1:3000`
- `/api`、`/media`、`/ws` 都通过 Vite 代理转发到 `127.0.0.1:8000`
- 因此前端联调时，后端应保持运行在 `127.0.0.1:8000`

---

## 7. 推荐启动顺序（最短路径）

### 7.1 第一次启动

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
npm --prefix frontend install
```

然后按第 3 节确认 `.env` 中的 `DEV_LOGIN_ENABLED=True` 与 `VITE_LOCAL_DEV_AUTH=true`。

### 7.2 日常启动

先开后端：

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

再开前端：

```powershell
cd frontend
npm run dev
```

---

## 8. 首个验证页面

推荐把下面这个地址作为 **第一验证页面**：

- `http://127.0.0.1:8000/api/docs/`

原因：

- 不依赖前端构建结果
- 不依赖开发态登录是否已切换完成
- 能最快确认 Django、路由、drf-spectacular 已正常工作

后端确认正常后，再打开前端：

- `http://127.0.0.1:3000/home`

如果 `.env` 中 `DEV_LOGIN_ENABLED=True` 和 `VITE_LOCAL_DEV_AUTH=true` 已生效，页面应停留在 `/home`，并显示已登录用户 `local-dev`；浏览器控制台应无错误。

---

## 9. 开发态认证说明

当前本地开发自动登录契约如下：

- 接口：`POST /api/auth/dev-login/`
- 后端显式开关：`DEV_LOGIN_ENABLED`
- 前端显式开关：`VITE_LOCAL_DEV_AUTH`

如果你需要在**可信任的本地开发环境**启用这条链路，请在 `.env` 中同时设置：

```env
DEV_LOGIN_ENABLED=True
VITE_LOCAL_DEV_AUTH=true
```

说明：

- 两个开关需要同时对齐；只开一侧时，前端可能仍会回到登录页或出现 `401`
- 如果你从 `.env.example` 复制，请确认使用的真实键名就是 `DEV_LOGIN_ENABLED` 和 `VITE_LOCAL_DEV_AUTH`
- 修改 `VITE_LOCAL_DEV_AUTH` 后，需要**重启 Vite 开发服务器**（重新在 `frontend` 目录执行 `npm run dev`）才会读取新的 `VITE_` 变量
- 验证成功时，访问 `http://127.0.0.1:3000/home` 应停留在 `/home`，并显示 `local-dev`

`.env.example` 已为这组开发认证开关预留注释位，但默认保持关闭。

---

## 10. 已知限制

当前 README 明确保留以下限制：

1. **最小本地开发仅覆盖 SQLite 路径**  
   MySQL 不是本 README 的默认启动方式；只有在你明确需要验证 MySQL 行为时再切换。

2. **开发态自动登录依赖显式开关**  
   当前本地最小前端联调路径使用 `POST /api/auth/dev-login/`；需要后端 `DEV_LOGIN_ENABLED` 与前端 `VITE_LOCAL_DEV_AUTH` 同时对齐，修改 `VITE_LOCAL_DEV_AUTH` 后需要重启 Vite。

3. **Vite 代理当前默认指向 `127.0.0.1:8000`**  
   如果你修改了 Django 端口，需要同步修改 `frontend/vite.config.js`，否则前端请求会打到错误地址。

4. **扩展模块不在最小 runbook 保证范围内**  
   例如 Redis/Celery、短信、邮件、AI 配置、App 自动化、浏览器驱动、Allure 等，可能需要额外环境或数据。

---

## 11. 故障排查

### 11.1 `Activate.ps1` 无法执行

执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 11.2 启动后端时仍尝试连 MySQL

先检查 `.env`：

```env
USE_SQLITE=True
```

如果你改过 `.env` 但终端没生效，关闭当前 shell 重新打开再试。

### 11.3 前端页面打开了，但接口请求失败

先确认：

- 后端是否真的运行在 `127.0.0.1:8000`
- `http://127.0.0.1:8000/api/docs/` 是否可打开

因为前端开发代理默认写死到 `127.0.0.1:8000`。

### 11.4 出现 401 / 登录循环 / 跳回登录页

这通常与当前开发态认证切换有关：

- 先确认后端 API 文档页正常
- 再确认 `.env` 中后端开关是否为 `DEV_LOGIN_ENABLED=True`
- 再确认前端使用的变量名是否为 `VITE_LOCAL_DEV_AUTH=true`
- 如果你刚修改过 `VITE_LOCAL_DEV_AUTH`，需要重启 `frontend` 目录下的 `npm run dev`
- 如果访问 `http://127.0.0.1:3000/home` 后没有停留在 `/home`，或页面没有显示 `local-dev`，优先检查以上两项开关是否真的生效

### 11.5 本地 SQLite 数据异常或迁移状态混乱

如果这是你的本地临时开发库，并且不需要保留数据，可以：

1. 备份当前 `db.sqlite3`
2. 删除本地副本
3. 重新执行：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

> 仅对你自己的本地临时数据库这样做；不要误删团队共享数据。

---

## 12. 一页命令速查

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
# 第一个终端（仓库根目录）
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
# 第二个终端
npm --prefix frontend install
cd frontend
npm run dev
```

---

如果你只想判断“本地有没有跑起来”，请按这个顺序看：

1. `http://127.0.0.1:8000/api/docs/`
2. `http://127.0.0.1:3000/home`
