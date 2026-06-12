import { defineStore } from "pinia";
import { ref, computed } from "vue";
import api from "@/utils/api";
import { track } from "@/utils/tracker";

const LOCAL_DEV_AUTH_ENABLED = import.meta.env.VITE_LOCAL_DEV_AUTH === "true";
const DEV_LOGIN_ENDPOINT = "/auth/dev-login/";
const LEGACY_LOCAL_DEV_ACCESS_TOKEN = "local-dev-access-token";
const LEGACY_LOCAL_DEV_REFRESH_TOKEN = "local-dev-refresh-token";
const ACCESS_TOKEN_TTL_MS = 30 * 60 * 1000;

export const useUserStore = defineStore("user", () => {
  const user = ref(null);
  const accessToken = ref(localStorage.getItem("access_token") || "");
  const refreshToken = ref(localStorage.getItem("refresh_token") || "");
  const tokenExpiresAt = ref(
    parseInt(localStorage.getItem("token_expires_at") || "0", 10),
  );

  let refreshTimer = null;
  let isLoggingOut = false;
  let devLoginPromise = null;

  const hasLegacyLocalDevAuth = () => {
    return (
      accessToken.value === LEGACY_LOCAL_DEV_ACCESS_TOKEN ||
      refreshToken.value === LEGACY_LOCAL_DEV_REFRESH_TOKEN
    );
  };

  const clearAuthStorage = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("token_expires_at");
    localStorage.removeItem("user");
  };

  const clearAuthState = () => {
    accessToken.value = "";
    refreshToken.value = "";
    user.value = null;
    tokenExpiresAt.value = 0;
    clearAuthStorage();
  };

  const persistAuth = () => {
    if (accessToken.value) {
      localStorage.setItem("access_token", accessToken.value);
    } else {
      localStorage.removeItem("access_token");
    }

    if (refreshToken.value) {
      localStorage.setItem("refresh_token", refreshToken.value);
    } else {
      localStorage.removeItem("refresh_token");
    }

    if (tokenExpiresAt.value) {
      localStorage.setItem("token_expires_at", tokenExpiresAt.value.toString());
    } else {
      localStorage.removeItem("token_expires_at");
    }

    if (user.value) {
      localStorage.setItem("user", JSON.stringify(user.value));
    } else {
      localStorage.removeItem("user");
    }
  };

  const applyAuthPayload = (payload) => {
    accessToken.value = payload.access;
    refreshToken.value = payload.refresh;
    user.value = payload.user;
    tokenExpiresAt.value = Date.now() + ACCESS_TOKEN_TTL_MS;
    persistAuth();
    return payload;
  };

  const ensureLocalDevAuth = async () => {
    if (!LOCAL_DEV_AUTH_ENABLED) {
      return null;
    }

    if (hasLegacyLocalDevAuth()) {
      clearAuthState();
    }

    if (accessToken.value && refreshToken.value) {
      return {
        access: accessToken.value,
        refresh: refreshToken.value,
        user: user.value,
      };
    }

    if (devLoginPromise) {
      return devLoginPromise;
    }

    devLoginPromise = (async () => {
      const response = await api.post(DEV_LOGIN_ENDPOINT, {});
      return applyAuthPayload(response.data);
    })();

    try {
      return await devLoginPromise;
    } finally {
      devLoginPromise = null;
    }
  };

  if (hasLegacyLocalDevAuth()) {
    clearAuthState();
  }

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value);

  const isTokenExpiringSoon = computed(() => {
    if (!tokenExpiresAt.value) return false;
    const now = Date.now();
    const timeLeft = tokenExpiresAt.value - now;
    return timeLeft < 5 * 60 * 1000;
  });

  const isTokenExpired = computed(() => {
    if (!tokenExpiresAt.value) return false;
    return Date.now() > tokenExpiresAt.value;
  });

  const startAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    refreshTimer = setInterval(
      async () => {
        if (
          refreshToken.value &&
          isTokenExpiringSoon.value &&
          accessToken.value
        ) {
          try {
            await refreshAccessToken();
          } catch (error) {
            console.error("自动刷新 token 失败:", error);
          }
        }
      },
      2 * 60 * 1000,
    );
  };

  const stopAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  };

  const login = async (credentials) => {
    try {
      const response = await api.post("/auth/login/", credentials);

      applyAuthPayload(response.data);
      startAutoRefresh();

      track("login_success", {
        event_type: "business",
        module: "auth",
        page_path: "/login",
        success: true,
        metadata: {
          login_type: "password",
        },
      });

      return response.data;
    } catch (error) {
      throw error;
    }
  };

  const smsLogin = async (data) => {
    try {
      const response = await api.post("/auth/sms-login/", data);

      applyAuthPayload(response.data);
      startAutoRefresh();

      track("login_success", {
        event_type: "business",
        module: "auth",
        page_path: "/login",
        success: true,
        metadata: {
          login_type: "sms",
        },
      });

      return response.data;
    } catch (error) {
      throw error;
    }
  };

  const register = async (userData) => {
    try {
      const response = await api.post("/auth/test-register/", userData);

      applyAuthPayload(response.data);
      startAutoRefresh();

      track("register_success", {
        event_type: "business",
        module: "auth",
        page_path: "/register",
        success: true,
      });

      return response.data;
    } catch (error) {
      throw error;
    }
  };

  const logout = async () => {
    stopAutoRefresh();

    if (isLoggingOut) {
      return;
    }
    isLoggingOut = true;

    try {
      if (refreshToken.value && !isTokenExpired.value) {
        try {
          await api.post("/auth/logout/", { refresh: refreshToken.value });
        } catch (apiError) {
          console.error("Logout API 调用失败:", apiError);
        }
      }
    } finally {
      clearAuthState();
      isLoggingOut = false;
      window.location.href = "/home";
    }
  };

  const refreshAccessToken = async () => {
    try {
      const response = await api.post("/auth/token/refresh/", {
        refresh: refreshToken.value,
      });

      accessToken.value = response.data.access;
      tokenExpiresAt.value = Date.now() + ACCESS_TOKEN_TTL_MS;

      if (response.data.refresh) {
        refreshToken.value = response.data.refresh;
      }

      persistAuth();
      return response.data.access;
    } catch (error) {
      console.error("Token refresh failed:", error);
      await logout();
      throw error;
    }
  };

  const fetchUser = async () => {
    try {
      const response = await api.get("/users/me/");
      user.value = response.data;
      persistAuth();
      return response.data;
    } catch (error) {
      await logout();
      throw error;
    }
  };

  const fetchProfile = async () => {
    try {
      const response = await api.get("/auth/profile/");
      user.value = response.data;
      persistAuth();
      return response.data;
    } catch (error) {
      if (error.response?.status === 401) {
        await logout();
      }
      throw error;
    }
  };

  const initAuth = async () => {
    if (hasLegacyLocalDevAuth()) {
      clearAuthState();
    }

    if (!user.value) {
      const savedUser = localStorage.getItem("user");
      if (savedUser) {
        try {
          user.value = JSON.parse(savedUser);
        } catch (error) {
          console.error("解析用户信息失败:", error);
        }
      }
    }

    if (LOCAL_DEV_AUTH_ENABLED && !accessToken.value) {
      try {
        await ensureLocalDevAuth();
      } catch (error) {
        console.error("获取本地开发 JWT 失败:", error);
        clearAuthState();
        throw error;
      }
    }

    if (accessToken.value) {
      if (isTokenExpired.value && refreshToken.value) {
        try {
          await refreshAccessToken();
        } catch (error) {
          console.error("Token 刷新失败:", error);
          return null;
        }
      }

      if (!user.value) {
        try {
          await fetchProfile();
        } catch (error) {
          console.error("获取用户信息失败:", error);
          await logout();
          return null;
        }
      }

      startAutoRefresh();
    }

    return user.value;
  };

  return {
    user,
    accessToken,
    refreshToken,
    tokenExpiresAt,
    isAuthenticated,
    isTokenExpiringSoon,
    isTokenExpired,
    login,
    smsLogin,
    register,
    logout,
    refreshAccessToken,
    fetchProfile,
    initAuth,
    startAutoRefresh,
    stopAutoRefresh,
  };
});
