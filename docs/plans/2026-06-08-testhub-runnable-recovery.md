# Tongdaxin Testing Platform Runnable Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a locally runnable Tongdaxin Testing Platform development workflow in `g:\Working\AI_Work\testhub_platform`, with backend + frontend + SQLite working together and README updated with verified startup steps.

**Architecture:** Prefer the lowest-friction local development path: Django on `127.0.0.1:8000`, Vite on `127.0.0.1:3000`, SQLite enabled through `.env`, and a consistent development authentication path so frontend dev mode can call protected backend APIs successfully. Preserve the current dirty worktree and make only surgical fixes needed for local runnability and documentation accuracy.

**Tech Stack:** Django 4.2, DRF + SimpleJWT, Vue 3 + Vite 7, SQLite/MySQL dual config, Playwright smoke verification.

---

### Task 1: Lock the minimal local run target

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Reference: `.env`
- Reference: `backend/settings.py`
- Reference: `frontend/vite.config.js`

**Step 1: Confirm the verified local target**

- Backend dev server: `127.0.0.1:8000`
- Frontend dev server: `127.0.0.1:3000`
- Database: SQLite via `USE_SQLITE=True`
- Verified endpoints: `/api/schema/`, `/api/docs/`
- Verified frontend entry: `/home`

**Step 2: Capture the real blockers**

- README text encoding is broken and cannot be trusted as-is.
- Frontend build passes, but data pages return `401`.
- Root cause: frontend local-dev session bypass and backend JWT requirement are inconsistent.
- SQLite migrations are already fully applied.

**Step 3: Define the required outcome**

- Local dev must support entering a data-backed page such as `/ai-generation/projects` without `401`.
- Startup instructions must no longer assume MySQL or SMS registration is required for first local run.

**Step 4: Verification**

Run:

```bash
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py showmigrations
npm --prefix frontend run build
```

Expected:
- Django check passes
- All migrations applied
- Frontend build passes

---

### Task 2: Repair development authentication alignment

**Files:**
- Modify: `frontend/src/stores/user.js`
- Modify: `frontend/src/utils/api.js`
- Modify: `frontend/src/router/index.js` (only if route guarding must change)
- Modify: `apps/users/views.py`
- Modify: `apps/users/urls.py`
- Optional: `backend/settings.py`

**Step 1: Choose one consistent dev auth strategy**

Preferred outcome:
- Keep convenient local development access
- But acquire a real backend JWT before protected API calls

Preferred implementation direction:
- Add a debug-only/dev-only backend token bootstrap endpoint or equivalent local JWT bootstrap path
- Make frontend dev mode exchange/bootstrap a real JWT instead of only fabricating local user state

Avoid:
- Blanket removal of authentication from protected APIs
- Permanent weakening of production auth
- Requiring SMS registration for first local startup

**Step 2: Implement the smallest secure dev path**

Possible acceptance shape:
- Frontend dev init requests a dedicated dev-auth endpoint
- Backend creates/fetches a local development user only in safe development conditions
- Backend returns normal JWT access/refresh pair
- Frontend stores those tokens and continues through the existing authenticated API flow

**Step 3: Verify the fixed path**

Run:

```bash
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
npm --prefix frontend run dev -- --host 127.0.0.1 --port 3000
```

Then verify:
- Open `http://127.0.0.1:3000/ai-generation/projects`
- No `401` on `/api/projects/`
- Page renders normally

---

### Task 3: Reconcile environment and cross-module config

**Files:**
- Modify: `.env.example`
- Modify: `backend/settings.py` (only if needed for explicit dev flag parsing)
- Modify: `frontend/vite.config.js` (only if proxy/env handling must change)
- Optional: `frontend/package.json`

**Step 1: Normalize local defaults**

- Document Vite `3000` and Django `8000`
- Ensure CORS/CSRF defaults match local dev ports
- Ensure README/.env.example describe SQLite as the default local path

**Step 2: Make any new dev auth flag explicit**

Examples:
- Backend: `DEV_BOOTSTRAP_AUTH=True`
- Frontend: `VITE_LOCAL_DEV_AUTH=true`

The exact flag names can differ, but they must be explicit and documented instead of being silently tied to `import.meta.env.DEV` alone.

**Step 3: Verification**

Run:

```bash
npm --prefix frontend run build
.venv\Scripts\python.exe manage.py check
```

Expected:
- No new config regressions
- Proxy and auth bootstrap path still resolve under Vite dev server

---

### Task 4: Rewrite README into a verified local runbook

**Files:**
- Modify: `README.md`

**Step 1: Fix README encoding/content**

- Replace broken mojibake text with UTF-8 readable content
- Keep concise focus on local startup first

**Step 2: Document the verified flow**

Include:
- Python / Node versions actually used successfully
- Virtualenv activation
- `pip install -r requirements.txt`
- `.env` setup
- SQLite local mode
- Backend startup
- Frontend startup
- First smoke URLs
- Known optional dependencies (MySQL, Redis, SMS, browser drivers)

**Step 3: Add troubleshooting**

At minimum:
- `401` on protected API in dev mode
- README encoding issue
- MySQL vs SQLite selection
- Vite proxy/backend port mismatch

---

### Task 5: Produce the final smoke test report

**Files:**
- Create: `docs/plans/2026-06-08-testhub-runnable-test-report.md` (optional staging artifact)

**Step 1: Backend smoke**

Verify:
- `GET /api/schema/` → `200`
- `GET /api/docs/` → `200`

**Step 2: Frontend smoke**

Verify:
- `GET /` on Vite dev server loads
- `/home` renders
- One authenticated data page renders without `401`

**Step 3: Final report content**

Record:
- What commands were run
- What passed
- What warnings remain (for example schema-generation warnings)
- What remains optional/non-blocking

