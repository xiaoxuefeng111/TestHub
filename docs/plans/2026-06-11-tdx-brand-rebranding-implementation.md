# Tongdaxin Brand Rebranding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebrand the project’s visible `Tongdaxin Testing Platform` surfaces to `通达信测试平台` / `Tongdaxin Testing Platform`, wire in the user-provided logo, and preserve compatibility for internal keys and configuration defaults.

**Architecture:** Keep the repository structure, Django app names, Python imports, and project directory unchanged. Apply the rebrand in layers: first assets and visible frontend strings, then backend/API/report branding, then compatibility shims for storage keys and config defaults. Validate with targeted grep checks plus frontend/backend smoke commands.

**Tech Stack:** Vue 3, Vite, Element Plus, Vue I18n, Django, drf-spectacular, SimpleUI, Allure static plugin, PNG/SVG image assets, PowerShell, ripgrep.

---

## Pre-flight Notes

- The repository already has many unrelated uncommitted changes. Execute this plan by staging **only** the files listed in each task.
- Prefer the user-provided brand asset at:
  - `C:\Users\HP\AppData\Roaming\spectrai\attachments\2026-06\spectrai_img_20260611_1781179172091.png`
- Do **not** rename the repository root, Django apps, Python modules, import paths, or existing migration history.

### Task 1: Add branded image assets and wire the top-level frontend entry points

**Files:**
- Create: `frontend/src/assets/images/tdx-logo.png`
- Create: `frontend/src/assets/images/tdx-logo_home.png`
- Modify: `frontend/index.html`
- Modify: `frontend/src/layout/index.vue`
- Modify: `frontend/src/views/auth/Login.vue`

**Step 1: Capture the current frontend brand baseline**

Run: `rg -n -e "Tongdaxin Testing Platform" -e "AI-Powered Testing Platform" -e "logo.svg" -e "logo_home.png" frontend/index.html frontend/src/layout/index.vue frontend/src/views/auth/Login.vue`
Expected: matches in title, layout image imports, and login brand text.

**Step 2: Add the new image assets**

Copy the provided user logo to both frontend asset targets:

```powershell
Copy-Item "C:\Users\HP\AppData\Roaming\spectrai\attachments\2026-06\spectrai_img_20260611_1781179172091.png" "frontend/src/assets/images/tdx-logo.png"
Copy-Item "C:\Users\HP\AppData\Roaming\spectrai\attachments\2026-06\spectrai_img_20260611_1781179172091.png" "frontend/src/assets/images/tdx-logo_home.png"
```

**Step 3: Update the browser title and favicon**

In `frontend/index.html` set:

```html
<link rel="icon" href="/src/assets/images/tdx-logo.png" />
<title>通达信测试平台 - AI 一体化测试平台</title>
```

**Step 4: Update the main layout brand image usage**

In `frontend/src/layout/index.vue` replace the imports and alt text with:

```js
import logoSvg from "@/assets/images/tdx-logo.png";
import logoHomePng from "@/assets/images/tdx-logo_home.png";
```

```vue
<img :src="logoImage" alt="通达信测试平台" class="logo-img" />
```

**Step 5: Update the login header branding**

In `frontend/src/views/auth/Login.vue`:
- Replace `Tongdaxin Testing Platform` with `通达信测试平台`
- Replace `AI-Powered Testing Platform` with `AI 一体化测试平台`
- Replace the inline SVG block inside `.logo-icon` with an `<img>` tag pointing at `@/assets/images/tdx-logo.png`
- Keep the large title text so the small PNG is not stretched too aggressively

Suggested template:

```vue
<div class="logo-icon">
  <img :src="brandLogo" alt="通达信测试平台" />
</div>
<h1 class="brand-title">通达信测试平台</h1>
<p class="brand-subtitle">AI 一体化测试平台</p>
```

**Step 6: Verify the visible frontend brand strings**

Run: `rg -n -e "Tongdaxin Testing Platform" -e "AI-Powered Testing Platform" frontend/index.html frontend/src/layout/index.vue frontend/src/views/auth/Login.vue`
Expected: no matches.

**Step 7: Commit**

```bash
git add frontend/index.html frontend/src/layout/index.vue frontend/src/views/auth/Login.vue frontend/src/assets/images/tdx-logo.png frontend/src/assets/images/tdx-logo_home.png
git commit -m "feat: rebrand frontend entrypoints to tongdaxin"
```

### Task 2: Replace user-visible brand copy in i18n resources and home-facing views

**Files:**
- Modify: `frontend/src/locales/lang/zh-cn/auth.js`
- Modify: `frontend/src/locales/lang/zh-cn/project.js`
- Modify: `frontend/src/locales/lang/zh-cn/ui-automation.js`
- Modify: `frontend/src/locales/lang/en/auth.js`
- Modify: `frontend/src/locales/lang/en/project.js`
- Modify: `frontend/src/locales/lang/en/ui-automation.js`
- Modify: `frontend/src/views/Home.vue`

**Step 1: Write the failing copy audit**

Run: `rg -n -e "Tongdaxin Testing Platform" -e "testhub" frontend/src/locales/lang/zh-cn frontend/src/locales/lang/en frontend/src/views/Home.vue`
Expected: matches in auth/project/ui-automation locale files and the mobile tip storage key.

**Step 2: Update Chinese brand strings**

Apply these replacements:

```js
registerTitle: "注册 通达信测试平台"
title: "通达信测试平台"
mobileTipDesc: "本平台需在电脑浏览器中使用，请复制链接或切换至电脑打开通达信测试平台。"
```

Also update example copy in `zh-cn/ui-automation.js` from searching `Tongdaxin Testing Platform` to searching `通达信测试平台`.

**Step 3: Update English brand strings**

Apply these replacements:

```js
registerTitle: "Register Tongdaxin Testing Platform"
title: "Tongdaxin Testing Platform"
mobileTipDesc: "Tongdaxin Testing Platform must be used in a desktop browser. Please switch to a computer to continue."
```

Also update example copy in `en/ui-automation.js` from searching `Tongdaxin Testing Platform` to searching `Tongdaxin Testing Platform`.

**Step 4: Check `frontend/src/views/Home.vue` for any hard-coded visible brand labels**

If the page contains visible `Tongdaxin Testing Platform` text outside i18n, replace it with the new brand name. Do not touch unrelated mojibake lines beyond the brand-specific edits.

**Step 5: Re-run the audit**

Run: `rg -n -e "Tongdaxin Testing Platform" frontend/src/locales/lang/zh-cn frontend/src/locales/lang/en frontend/src/views/Home.vue`
Expected: no visible-brand matches remain in these files.

**Step 6: Commit**

```bash
git add frontend/src/locales/lang/zh-cn/auth.js frontend/src/locales/lang/zh-cn/project.js frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/auth.js frontend/src/locales/lang/en/project.js frontend/src/locales/lang/en/ui-automation.js frontend/src/views/Home.vue
git commit -m "feat: rebrand localized frontend copy"
```

### Task 3: Add compatibility shims for renamed frontend storage keys

**Files:**
- Modify: `frontend/src/utils/tracker.js`
- Modify: `frontend/src/views/Home.vue`

**Step 1: Write a failing compatibility check**

Run: `rg -n -e "testhub_analytics_session_id" -e "testhub_home_mobile_tip_seen" frontend/src/utils/tracker.js frontend/src/views/Home.vue`
Expected: both legacy key names are present.

**Step 2: Add new key constants plus legacy fallback for analytics**

In `frontend/src/utils/tracker.js` introduce:

```js
const SESSION_STORAGE_KEY = "tdx_analytics_session_id";
const LEGACY_SESSION_STORAGE_KEY = "testhub_analytics_session_id";
```

Update `getSessionId()` so it:
1. reads the new key first
2. falls back to the legacy key
3. if legacy is found, writes it back into the new key before returning it
4. generates a new ID only when neither exists

**Step 3: Add new key constants plus legacy fallback for the home mobile tip**

In `frontend/src/views/Home.vue` introduce:

```js
const MOBILE_TIP_STORAGE_KEY = "tdx_home_mobile_tip_seen";
const LEGACY_MOBILE_TIP_STORAGE_KEY = "testhub_home_mobile_tip_seen";
```

Update the read/write flow so:
- writes use `tdx_home_mobile_tip_seen`
- reads accept either the new key or the legacy key
- when the legacy key is found, mirror it into the new key

**Step 4: Verify the shim logic is in place**

Run: `rg -n -e "LEGACY_SESSION_STORAGE_KEY" -e "LEGACY_MOBILE_TIP_STORAGE_KEY" -e "tdx_analytics_session_id" -e "tdx_home_mobile_tip_seen" frontend/src/utils/tracker.js frontend/src/views/Home.vue`
Expected: both new and legacy constants appear.

**Step 5: Commit**

```bash
git add frontend/src/utils/tracker.js frontend/src/views/Home.vue
git commit -m "feat: add compatibility for renamed frontend storage keys"
```

### Task 4: Rebrand backend API/admin metadata while preserving config compatibility

**Files:**
- Modify: `backend/settings.py`
- Modify: `.env.example`

**Step 1: Write the failing backend audit**

Run: `rg -n -e "default='testhub'" -e "DB_NAME=testhub" -e "Tongdaxin Testing Platform API" -e "SIMPLEUI_LOGO" backend/settings.py .env.example`
Expected: matches for DB name default, env example, API title, and current logo setting.

**Step 2: Rebrand the API title**

In `backend/settings.py` change:

```python
'TITLE': '通达信测试平台 API',
'DESCRIPTION': 'Tongdaxin Testing Platform API',
```

**Step 3: Preserve DB compatibility while updating examples**

Keep runtime compatibility by continuing to read `DB_NAME` as-is. Update `.env.example` to show a new branded example value, such as:

```env
DB_NAME=tongdaxin_test_platform
```

Do **not** change Django database engine wiring or environment variable names in this task.

**Step 4: Point SimpleUI branding to a project-controlled resource**

Replace the external Django favicon URL with a stable local/static brand resource reference that SimpleUI can access in this project. If necessary, add a static asset later, but the final setting must not depend on `https://static.djangoproject.com/...`.

**Step 5: Re-run the backend audit**

Run: `rg -n -e "Tongdaxin Testing Platform API" -e "DB_NAME=testhub" backend/settings.py .env.example`
Expected: no matches.

**Step 6: Validate Django settings load**

Run: `python manage.py check`
Expected: `System check identified no issues` or equivalent success output.

**Step 7: Commit**

```bash
git add backend/settings.py .env.example
git commit -m "feat: rebrand backend metadata and config examples"
```

### Task 5: Rebrand the Allure custom logo plugin

**Files:**
- Create: `allure/plugins/custom-logo-plugin/static/tdx-logo.png`
- Modify: `allure/plugins/custom-logo-plugin/static/styles.css`
- Optionally replace: `allure/plugins/custom-logo-plugin/static/custom-logo.svg`

**Step 1: Capture the current report-brand baseline**

Run: `rg -n -e "custom-logo.svg" -e "side-nav__brand" allure/plugins/custom-logo-plugin/static/styles.css`
Expected: CSS points to `custom-logo.svg`.

**Step 2: Add the Tongdaxin report logo asset**

Copy the user-provided PNG into the report plugin static directory:

```powershell
Copy-Item "C:\Users\HP\AppData\Roaming\spectrai\attachments\2026-06\spectrai_img_20260611_1781179172091.png" "allure/plugins/custom-logo-plugin/static/tdx-logo.png"
```

**Step 3: Update the plugin CSS to use the new image**

Set the background image to the new PNG and tune sizing explicitly, e.g.:

```css
.side-nav__brand {
  background: url('tdx-logo.png') no-repeat left center !important;
  background-size: 24px 24px;
  margin-left: 10px;
}
```

If the brand text area collapses visually, add `padding-left` or height rules so the icon remains legible.

**Step 4: Verify the static brand reference**

Run: `rg -n -e "tdx-logo.png" -e "custom-logo.svg" allure/plugins/custom-logo-plugin/static/styles.css`
Expected: `tdx-logo.png` present; `custom-logo.svg` absent unless intentionally kept as fallback.

**Step 5: Commit**

```bash
git add allure/plugins/custom-logo-plugin/static/styles.css allure/plugins/custom-logo-plugin/static/tdx-logo.png
git commit -m "feat: rebrand allure custom logo"
```

### Task 6: Run final regression checks and produce a residual-brand inventory

**Files:**
- Review only: `frontend/index.html`
- Review only: `frontend/src/layout/index.vue`
- Review only: `frontend/src/views/auth/Login.vue`
- Review only: `frontend/src/locales/lang/zh-cn/*.js`
- Review only: `frontend/src/locales/lang/en/*.js`
- Review only: `frontend/src/utils/tracker.js`
- Review only: `frontend/src/views/Home.vue`
- Review only: `backend/settings.py`
- Review only: `.env.example`
- Review only: `allure/plugins/custom-logo-plugin/static/styles.css`

**Step 1: Run the targeted brand scan**

Run: `rg -n --hidden --glob '!node_modules/**' --glob '!.git/**' -e "Tongdaxin Testing Platform" -e "testhub" frontend/index.html frontend/src backend/settings.py .env.example allure/plugins/custom-logo-plugin`
Expected: only intentional compatibility keys or non-user-facing leftovers remain.

**Step 2: Build-check the frontend**

Run: `npm run build`
Workdir: `frontend`
Expected: successful Vite production build.

**Step 3: Run the backend check**

Run: `python manage.py check`
Expected: Django system check passes.

**Step 4: Manually inspect the highest-value UI entry points**

Verify these visible outcomes:
- browser title shows `通达信测试平台 - AI 一体化测试平台`
- login page shows the Tongdaxin logo, `通达信测试平台`, and `AI 一体化测试平台`
- left navigation logo uses the new brand image
- Swagger / API docs title shows `通达信测试平台 API`
- Allure side-nav brand icon shows the Tongdaxin logo

**Step 5: Record the residual inventory**

If `rg` still finds `testhub`, classify each remaining hit as one of:
- compatibility key
- repository path / directory name
- historical doc
- deployment script / service name
- not-in-scope technical identifier

Do not chase non-scope hits in this task.

**Step 6: Commit**

```bash
git add frontend/index.html frontend/src/layout/index.vue frontend/src/views/auth/Login.vue frontend/src/locales/lang/zh-cn/auth.js frontend/src/locales/lang/zh-cn/project.js frontend/src/locales/lang/zh-cn/ui-automation.js frontend/src/locales/lang/en/auth.js frontend/src/locales/lang/en/project.js frontend/src/locales/lang/en/ui-automation.js frontend/src/utils/tracker.js frontend/src/views/Home.vue backend/settings.py .env.example allure/plugins/custom-logo-plugin/static/styles.css allure/plugins/custom-logo-plugin/static/tdx-logo.png frontend/src/assets/images/tdx-logo.png frontend/src/assets/images/tdx-logo_home.png
git commit -m "feat: rebrand app surfaces to tongdaxin"
```

## Execution Notes

- Use `rg` for content search and residual audits.
- Use MCP file-writing tools for text edits.
- When copying the PNG brand asset, preserve the original filename separately only if a fallback is needed.
- Avoid editing unrelated mojibake text outside the specific brand substitutions in this plan.
