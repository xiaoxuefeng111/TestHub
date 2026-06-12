# Mobile Login Tap Safety Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复移动端“点击交易登录”误点标题且被错误的点击后消失校验误判失败的问题。

**Architecture:** 保留现有 `tap_text` / `wait_text` 执行模型，只缩小自动后置校验的适用范围，并为“交易登录”这类底部主按钮补充更稳的点击区域约束。这样既能消除错误失败，也能降低点到顶部同名标题的概率。

**Tech Stack:** Django, Python unittest, Airtest runner, Android UI hierarchy helper

---

### Task 1: 修正 planner 对登录按钮的自动后置校验

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing test**

新增一个测试，断言 `点击交易登录按钮` 生成的 `tap_text` 步骤仍然保留 `index == -1`，但不再自动附加 `post_absent_text == '交易登录'`。

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/ui_automation/tests/test_mobile_agent.py -k trade_login -v`
Expected: FAIL，因为当前实现仍会自动附加 `post_absent_text`。

**Step 3: Write minimal implementation**

在 `_annotate_post_tap_validations()` 中排除登录类目标的自动消失校验，仅保留 `post_wait_text` 推断。

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/ui_automation/tests/test_mobile_agent.py -k trade_login -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "fix: avoid auto absent check for login tap"
```

### Task 2: 为登录类按钮添加更稳的点击区域约束

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing test**

新增一个测试，断言 `点击交易登录按钮` 生成的 `tap_text` 步骤包含底部区域约束（例如 `region` 覆盖屏幕下半区）。

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/ui_automation/tests/test_mobile_agent.py -k trade_login_region -v`
Expected: FAIL，因为当前实现没有注入区域约束。

**Step 3: Write minimal implementation**

在 planner 中为登录/提交/确认类主按钮注入默认底部点击区域，减少与顶部标题重名时的误点。

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/ui_automation/tests/test_mobile_agent.py -k trade_login_region -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "fix: bias login tap to bottom region"
```

### Task 3: 回归 runner 侧相关行为

**Files:**
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Verify existing runner tests still cover post-wait / post-absent behavior**

检查 runner 侧现有测试无需改动即可覆盖保留逻辑。

**Step 2: Run targeted tests**

Run: `python -m pytest apps/ui_automation/tests/test_mobile_agent.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`
Expected: PASS

**Step 3: Optional manual regression**

重新执行移动端 13 步交易登录流程，确认不再出现“点击后目标文字仍可见: 交易登录”，且点击坐标落在底部按钮区域。
