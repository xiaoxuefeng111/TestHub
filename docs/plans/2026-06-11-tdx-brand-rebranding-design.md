# 通达信测试平台品牌改造设计文档

**日期**: 2026-06-11  
**目标项目**: `g:\Working\AI_Work\testhub_platform`

## 1. 目标

将当前开源项目中面向用户可见的 `Tongdaxin Testing Platform` / `testhub` 品牌统一替换为 **通达信测试平台**，并接入用户提供的通达信品牌图标。在保持现有开发、启动、部署兼容性的前提下，尽可能清理低风险内部品牌痕迹；对数据库名、环境变量、脚本名等高风险内部标识采用“兼容过渡”策略，而非一次性硬切。

## 2. 用户确认的品牌信息

- 中文主品牌名：**通达信测试平台**
- 中文副标题：**AI 一体化测试平台**
- 英文品牌名：**Tongdaxin Testing Platform**
- Logo 来源：用户提供的 PNG 文件（小尺寸，适合 favicon / 导航小图标 / 报告小图标）

## 3. 设计原则

1. **对外彻底品牌化**：浏览器标题、登录页、导航栏、接口文档、报告页、主要中英文文案不再出现 `Tongdaxin Testing Platform`。
2. **内部兼容优先**：数据库默认值、环境变量、脚本引用、前端存储 key 等高风险项不做激进硬改，优先支持新旧兼容。
3. **最小化破坏**：不修改仓库目录名、Python 包路径、Django app 名、迁移历史和 import 路径。
4. **分层落地**：先改品牌资源与可见入口，再改低风险内部标识，最后处理兼容项。

## 4. 改造范围

### 4.1 对外品牌层（必须改）

#### 前端入口与页面
- `frontend/index.html`
  - 页面 `<title>` 改为 `通达信测试平台 - AI 一体化测试平台`
  - favicon 指向通达信图标资源
- `frontend/src/layout/index.vue`
  - 左上角 logo 资源替换
  - `alt` 文案改为通达信相关
- `frontend/src/views/auth/Login.vue`
  - `Tongdaxin Testing Platform` 改为 `通达信测试平台`
  - `AI-Powered Testing Platform` 改为 `AI 一体化测试平台`
  - 将现有内联 SVG 品牌图形改为通达信 logo 显示
- `frontend/src/views/Home.vue`
  - 检查首页品牌展示与移动端提示文案中的品牌名
- `frontend/src/views/assistant/AssistantView.vue`
  - 检查是否需要同步品牌图形风格与标题文案

#### 国际化文案
重点修改包含品牌名的中英文资源：
- `frontend/src/locales/lang/zh-cn/auth.js`
- `frontend/src/locales/lang/zh-cn/project.js`
- `frontend/src/locales/lang/zh-cn/ui-automation.js`
- `frontend/src/locales/lang/en/auth.js`
- `frontend/src/locales/lang/en/project.js`
- `frontend/src/locales/lang/en/ui-automation.js`
- 如有其他可见页面中直接写死 `Tongdaxin Testing Platform`，一并替换

#### 后台与接口文档
- `backend/settings.py`
  - `SPECTACULAR_SETTINGS['TITLE']` 改为通达信品牌
  - `SIMPLEUI_LOGO` 切换为本地可控品牌资源，避免继续引用 Django 官方 favicon

#### 报告页品牌
- `allure/plugins/custom-logo-plugin/static/custom-logo.svg` 或等效品牌资源
- `allure/plugins/custom-logo-plugin/static/styles.css`
  - 替换 Allure 品牌展示图

### 4.2 内部低风险标识层（尽量改）

- `frontend/package.json`
  - `description` 改为通达信品牌描述
- `frontend/src/utils/tracker.js`
  - session key 改为通达信命名，并兼容旧 key 读取
- `frontend/src/views/Home.vue`
  - `testhub_home_mobile_tip_seen` 等存储 key 改名并兼容旧值
- `.env.example`
  - 示例文案与注释改为通达信品牌
- 文档中直接面向用户的品牌描述可逐步替换（本轮优先改关键入口，非核心长文档可后续分批清理）

### 4.3 内部高风险标识层（保留兼容，不硬改）

本轮**不直接改动**以下内容的基础结构：
- 仓库目录名：`testhub_platform`
- Python 包路径、Django app 名、import 语句
- 历史 migration 文件内的结构标识
- 可能影响现有部署的 service 文件名、脚本文件名、容器名、路径名

但会做以下兼容处理：
- `backend/settings.py` 中数据库默认值读取逻辑支持新旧命名过渡
- 旧环境变量名继续可用
- 旧前端 localStorage/sessionStorage key 可回读迁移

## 5. Logo 资源策略

用户提供的是一张小尺寸 PNG，适合小图标场景，不适合大面积无损放大。为降低视觉风险：

1. 小尺寸场景直接使用：
   - favicon
   - 左上角导航 logo
   - Allure 报告 logo
2. 大尺寸场景采用“logo + 文字”组合：
   - 登录页显示通达信 logo + 大标题 `通达信测试平台`
   - 避免仅放大位图导致模糊
3. 若后续拿到高分辨率或矢量版 logo，可再替换登录页和欢迎页资源

## 6. 兼容性策略

### 6.1 数据库/环境变量
- 当前 `backend/settings.py` 默认数据库名为 `testhub`
- 本轮优先方案：支持新的品牌默认示例，但不强制破坏旧 `.env` 与现有数据库配置
- 如需改默认值，应保留旧值兼容入口，确保本地环境仍能启动

### 6.2 前端存储 key
- 对 `testhub_analytics_session_id`、`testhub_home_mobile_tip_seen` 等 key：
  - 写入新 key
  - 读取时兼容旧 key
  - 如成功读到旧 key，可在运行时迁移到新 key

### 6.3 后台 logo 资源
- 后台 `SIMPLEUI_LOGO` 目前引用外部地址
- 改造后使用项目内静态资源或稳定可控资源，避免外链依赖

## 7. 不在本轮范围内的事项

- 仓库根目录与工程名重命名
- Django/Python 模块名整体重构
- 所有历史文档与脚本示例的彻底品牌清洗
- 数据库物理库名与线上服务名的强制切换
- 自动生成新矢量 logo

## 8. 验收标准

### 8.1 可见品牌验收
以下入口不再显示 `Tongdaxin Testing Platform`：
- 浏览器标题
- 登录页主品牌名
- 登录页副标题
- 左上角导航品牌图标/说明
- 主要中英文品牌文案
- Swagger / OpenAPI 文档标题
- Allure 报告 logo

### 8.2 兼容性验收
- 旧环境配置不因品牌修改而直接失效
- 数据库默认配置与本地启动流程不被硬性破坏
- 前端旧存储 key 至少可被兼容读取

### 8.3 代码清理验收
- 关键代码入口的 `Tongdaxin Testing Platform` / `testhub` 命中显著下降
- 保留的 `testhub` 主要集中在兼容层、目录名、历史文档、脚本名或非本轮范围内容中

## 9. 实施顺序

1. 落品牌资源（logo / favicon / 报告 logo）
2. 修改前端入口与登录页
3. 修改中英文 i18n 品牌文案
4. 修改后端接口文档与后台品牌资源
5. 处理内部低风险 key / 描述文案
6. 对数据库名与配置示例做兼容性调整
7. 搜索回归检查并验证主要页面入口

## 10. 风险与应对

### 风险 1：logo 分辨率不足
- **应对**：登录页采用 logo + 大标题文字组合，避免大图拉伸失真

### 风险 2：仓库当前已有大量未提交改动
- **应对**：本次改动严格限定文件范围；提交时仅包含本次相关文件，不混入无关变更

### 风险 3：内部标识硬改导致启动/部署中断
- **应对**：高风险项采用兼容层，不碰 import 路径和工程目录名

## 11. 后续计划

基于本设计文档，下一步应生成一份可执行的 implementation plan，明确：
- 每个阶段修改哪些文件
- 哪些位置做兼容逻辑
- 如何验证页面与配置是否仍正常工作
- 哪些命中留待后续品牌清理迭代
