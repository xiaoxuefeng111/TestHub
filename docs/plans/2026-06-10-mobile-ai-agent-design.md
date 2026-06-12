# Mobile AI Agent 设计方案

**目标**：把现有“AI 智能测试”页面从浏览器文本代理扩展为可直接驱动 Android 真机的手机 AI 执行入口，首版支持自然语言任务、自主拆解、OCR 找字点击/等待、输入、滑动和结果回传。

## 现状结论
- 现有 `ui_automation` AI 链路只支持 `BrowserAgent` 与 `execution_mode=text`。
- 现有 `app_automation` 已具备 Android 设备管理、Airtest 连接和 `UiFlowRunner` 执行能力。
- 现有 `UiFlowRunner` 更擅长图片/坐标驱动，不足以支撑“按屏幕文字自主操作”。

## 方案选择
### 方案 A：继续走浏览器式 Agent
- 优点：复用 AI 执行记录和日志回传逻辑最多。
- 缺点：手机端缺少 DOM/元素树，无法直接平移 `browser-use`。

### 方案 B：自然语言规划 + OCR 文字动作 + Airtest 执行（采用）
- 先用现有 LLM 拆出业务步骤。
- 再把自然语言任务转换为受限 `ui_flow` JSON。
- 扩展 `UiFlowRunner` 支持 `start_app / tap_text / wait_text / swipe_until_text / keyevent / assert_text_visible` 等 OCR 驱动动作。
- 用新的 Mobile Executor 连接设备、启动应用、执行 flow、回传日志和状态。

### 方案 C：直接接入多模态实时看屏 Agent
- 优点：更接近真正的自主体。
- 缺点：需要稳定的视觉模型、截图多轮推理、动作纠偏机制，首版风险过高。

## 首版范围
- 平台：Android
- 页面：现有 `frontend/src/views/ui-automation/ai/AITesting.vue`
- 必填上下文：设备、应用包、任务描述
- 执行动作：启动应用、按文字点击、等待文字出现、输入文本、回车、方向滑动、滑动直到文字出现、截图、文字可见断言、返回键
- 记录：沿用 `AIExecutionRecord`，补充移动端目标信息

## 非目标
- iOS
- 模板图像采集与自动建库
- 多模态实时视觉纠偏
- 与 APP 测试用例编辑器完全融合

## 数据与接口设计
1. `AIExecutionRecord`
   - `execution_mode` 新增 `mobile`
   - 新增 `app_device`、`app_package`
2. `run_adhoc`
   - 接收 `device_id`、`app_package_id`
   - `execution_mode=mobile` 时走 Mobile Executor
3. 序列化与列表/详情页
   - 返回设备名、设备序列号、应用包名

## 执行链路
1. 前端提交任务 + 设备 + 应用包
2. 后端创建 `AIExecutionRecord(status=running, execution_mode=mobile)`
3. 后台线程启动 Mobile Executor
4. Mobile Executor
   - 设备校验/锁定
   - LLM 拆解步骤
   - LLM 生成受限 `ui_flow`
   - `AirtestBase.setup_airtest()`
   - `start_app(package)`
   - `UiFlowRunner.run(..., should_stop=...)`
   - 更新步骤状态、日志、结束状态
   - 释放设备

## 错误处理
- 设备不存在 / 被他人锁定：直接失败
- OCR 找不到文字：允许按动作级重试，最终失败写入日志
- 用户停止：在步骤边界停止并释放设备
- 应用未指定：前端阻止提交

## 测试策略
- 接口测试：`run_adhoc` mobile 分支创建记录并调起后台执行
- 执行器单测：`tap_text` 依据 OCR 命中坐标执行点击
- 执行器单测：`wait_text` 超时与命中路径

## 兼容性
- 原有 `execution_mode=text` 保持不变
- 原 Web AI 流程不回归
