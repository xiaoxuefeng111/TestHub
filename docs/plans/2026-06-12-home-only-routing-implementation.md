# Home-Only Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/home` the only public landing page and prevent the frontend from ever sending users to `/login` or `/register`.

**Architecture:** Keep the existing auth system and backend endpoints intact, but change frontend routing and auth-failure handling so unauthorized states always resolve to `/home`. Only `Home` becomes public; protected feature pages remain protected and bounce back to home instead of login.

**Tech Stack:** Vue 3, Vue Router 4, Pinia, Axios, Vite

---

### Task 1: Record failing regression scenario

**Files:**
- Modify: none
- Test: Browser automation against the running Vite app

**Step 1: Write the failing test**

Use this browser scenario as the regression case:
- Stop Django backend on `127.0.0.1:8000`
- Clear browser localStorage
- Visit `http://127.0.0.1:3000/api-testing/dashboard`
- Expect current behavior to be wrong: it lands on `/login`

**Step 2: Run test to verify it fails**

Expected: final URL is `/login`, proving the current app still exposes the login page as the unauthorized fallback.

**Step 3: No production change yet**

Do not modify source files until the failing behavior is observed.

**Step 4: Keep the failing output for comparison**

Record the final URL and page text.

**Step 5: Commit**

No commit for this task.

### Task 2: Update router entry points and auth guard

**Files:**
- Modify: `frontend/src/router/index.js`
- Test: Browser route navigation

**Step 1: Write the failing test**

Reuse Task 1 regression case plus these direct-entry checks:
- Visit `/login` and observe it does not stay on `/home`
- Visit `/register` and observe it does not stay on `/home`

**Step 2: Run test to verify it fails**

Expected: `/api-testing/dashboard` lands on `/login`; direct `/login` and `/register` still expose guest pages.

**Step 3: Write minimal implementation**

- Make `/home` public by removing `requiresAuth`
- Change `/login` and `/register` routes to redirect to `/home`
- Change the route guard fallback from `/login` to `/home`

**Step 4: Run test to verify it passes**

Expected:
- Unauthorized access to protected route ends on `/home`
- Direct `/login` and `/register` end on `/home`

**Step 5: Commit**

Suggested commit message:
`feat: route unauthorized users to home instead of login`

### Task 3: Update logout and 401 redirect targets

**Files:**
- Modify: `frontend/src/stores/user.js`
- Modify: `frontend/src/utils/api.js`
- Modify: `frontend/src/layout/index.vue`
- Modify: `frontend/src/views/Home.vue`
- Modify: `frontend/src/views/assistant/AssistantView.vue`

**Step 1: Write the failing test**

Define these expected behaviors:
- Logout should clear auth state and resolve to `/home`
- 401 / refresh failure should not send users to `/login`

**Step 2: Run test to verify it fails**

Expected: code paths still contain `/login` redirects or conditional `/login` navigation outside local-dev mode.

**Step 3: Write minimal implementation**

- Replace logout target `/login` with `/home`
- Replace axios 401 hard redirect `/login` with `/home`
- Replace UI component logout pushes with `/home`

**Step 4: Run test to verify it passes**

Expected: no auth-related redirect path points to `/login` anymore.

**Step 5: Commit**

Suggested commit message:
`refactor: unify auth fallbacks to home`

### Task 4: End-to-end verification

**Files:**
- Modify: none
- Test: Browser automation and manual route checks

**Step 1: Run protected-route regression again**

With backend stopped and localStorage cleared, visit `/api-testing/dashboard`.

**Step 2: Verify direct guest routes**

Visit `/login` and `/register`.

**Step 3: Verify with backend restored**

Start Django backend and visit `/home` and one protected page.

**Step 4: Confirm final behavior**

Expected:
- `/login` never appears as the fallback page
- `/register` never appears as the fallback page
- `/home` is always reachable
- Protected pages still require auth and bounce to `/home`

**Step 5: Commit**

Suggested commit message:
`test: verify home-only unauthenticated routing`
