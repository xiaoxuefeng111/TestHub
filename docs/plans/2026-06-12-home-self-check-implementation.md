# Home 自检按钮 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Home 页新增一个手动自检按钮，点击后检测 dev-login 链路并弹窗反馈后端是否正常。

**Architecture:** 前端只改 `Home.vue` 和 Home 文案文件。按钮触发一次独立的 axios 请求到 `/api/auth/dev-login/`，不复用现有登录状态；成功/失败结果在同一个弹窗里展示。桌面端放在右上角操作区，移动端放进下拉菜单。

**Tech Stack:** Vue 3、Element Plus、axios、vue-i18n

---

### Task 1: Add i18n copy

**Files:**
- Modify: `frontend/src/locales/lang/zh-cn/project.js`
- Modify: `frontend/src/locales/lang/en/project.js`

**Step 1: Add the new Home self-check strings**

Add keys for: `selfCheck`, `selfCheckTitle`, `selfCheckChecking`, `selfCheckSuccess`, `selfCheckFailed`, `selfCheckCheckingDetail`, `selfCheckDetailSuccess`, `selfCheckInvalidResponse`, `selfCheckNetworkError`, `selfCheckRetry`, `selfCheckClose`.

**Step 2: Verify the locale objects still export valid syntax**

Run: `cd frontend; npm run build`
Expected: Build proceeds past locale parsing.

### Task 2: Add the Home self-check UI and logic

**Files:**
- Modify: `frontend/src/views/Home.vue`

**Step 1: Write the new behavior in Home.vue**

- Add a desktop “自检” button in the header actions area.
- Add a mobile dropdown item for self-check.
- Add a dialog that shows checking / success / failure.
- Use a standalone axios call to `/api/auth/dev-login/` with a timeout.
- Treat 2xx + complete payload as success; otherwise show failure.

**Step 2: Verify the file builds**

Run: `cd frontend; npm run build`
Expected: Build succeeds with the new button/dialog.

### Task 3: Manual verification

**Files:**
- None

**Step 1: Verify backend-up path**

Open Home, click 自检, confirm the dialog reports success.

**Step 2: Verify failure path**

Stop the backend or make 8000 unavailable, click 自检 again, confirm the dialog reports backend unreachable / service error.

**Step 3: Commit**

```bash
git add frontend/src/views/Home.vue frontend/src/locales/lang/zh-cn/project.js frontend/src/locales/lang/en/project.js docs/plans/2026-06-12-home-self-check-design.md docs/plans/2026-06-12-home-self-check-implementation.md
git commit -m "feat: add home self-check button"
```