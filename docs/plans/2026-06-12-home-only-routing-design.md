# Home-Only Routing Design

**Date:** 2026-06-12

## Goal

前端不再向用户展示登录页或注册页。无论是直接访问 `/login`、未登录访问受保护页面、退出登录，还是 token 失效与鉴权失败场景，最终都统一落到 `/home`。

## Scope

- 前端路由重定向与守卫逻辑
- 前端退出登录后的跳转逻辑
- Axios 401 / refresh 失败后的跳转逻辑
- 保留现有登录/注册页面文件与后端认证接口，暂不做删除

## Non-Goals

- 不移除后端登录、注册、dev-login、refresh、logout 接口
- 不删除 `Login.vue`、`Register.vue`
- 不放开所有业务页面的鉴权访问；仅将未授权用户统一送回 `/home`

## Chosen Approach

采用“保留认证机制，但统一回到 `/home`”的方案。

1. 将 `/home` 设为公开入口，不要求登录。
2. 将 `/login` 与 `/register` 路由改为直接重定向到 `/home`。
3. 路由守卫中，原本所有未授权跳转到 `/login` 的逻辑统一改为 `/home`。
4. `logout()`、401 响应处理、refresh 失败处理中的目标地址统一改为 `/home`。
5. 页面组件中现有 `LOCAL_DEV_AUTH_ENABLED ? '/home' : '/login'` 的逻辑统一收敛为 `/home`，避免非开发环境仍落回登录页。

## Files Expected To Change

- `frontend/src/router/index.js`
- `frontend/src/stores/user.js`
- `frontend/src/utils/api.js`
- `frontend/src/layout/index.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/assistant/AssistantView.vue`

## Validation

1. 停掉后端、清空 localStorage，访问 `http://127.0.0.1:3000/api-testing/dashboard`，应跳到 `/home` 而不是 `/login`。
2. 直接访问 `http://127.0.0.1:3000/login`，应立即进入 `/home`。
3. 直接访问 `http://127.0.0.1:3000/register`，应立即进入 `/home`。
4. 点击退出登录后，应停留在 `/home`。
5. 后端恢复后，首页仍可访问，控制台不出现新的跳转错误。
