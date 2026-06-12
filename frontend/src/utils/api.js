import axios from "axios";
import { ElMessage } from "element-plus";
import { useUserStore } from "@/stores/user";

const LOCAL_DEV_AUTH_ENABLED = import.meta.env.VITE_LOCAL_DEV_AUTH === "true";
const DEV_LOGIN_ENDPOINT = "/auth/dev-login/";
const TOKEN_REFRESH_ENDPOINT = "/auth/token/refresh/";
const LOGOUT_ENDPOINT = "/auth/logout/";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

api.interceptors.request.use(
  async (config) => {
    const userStore = useUserStore();

    if (
      config.url === TOKEN_REFRESH_ENDPOINT ||
      config.url === DEV_LOGIN_ENDPOINT
    ) {
      return config;
    }

    if (LOCAL_DEV_AUTH_ENABLED && !userStore.accessToken) {
      try {
        await userStore.initAuth();
      } catch (error) {
        return Promise.reject(error);
      }
    }

    if (userStore.accessToken) {
      if (userStore.isTokenExpiringSoon && !userStore.isTokenExpired) {
        if (!isRefreshing) {
          isRefreshing = true;

          try {
            const newToken = await userStore.refreshAccessToken();
            processQueue(null, newToken);
            config.headers.Authorization = `Bearer ${newToken}`;
          } catch (error) {
            processQueue(error, null);
            return Promise.reject(error);
          } finally {
            isRefreshing = false;
          }
        } else {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then((token) => {
              config.headers.Authorization = `Bearer ${token}`;
              return config;
            })
            .catch((err) => {
              return Promise.reject(err);
            });
        }
      }

      config.headers.Authorization = `Bearer ${userStore.accessToken}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const userStore = useUserStore();
    const originalRequest = error.config || {};

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === LOGOUT_ENDPOINT) {
        userStore.$patch((state) => {
          state.accessToken = "";
          state.refreshToken = "";
          state.user = null;
          state.tokenExpiresAt = 0;
        });
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("token_expires_at");
        localStorage.removeItem("user");
        window.location.href = "/home";
        return Promise.reject(error);
      }

      if (originalRequest.url === TOKEN_REFRESH_ENDPOINT) {
        await userStore.logout();
        return Promise.reject(error);
      }

      if (originalRequest.url === DEV_LOGIN_ENDPOINT) {
        return Promise.reject(error);
      }

      if (userStore.refreshToken && !isRefreshing) {
        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const newToken = await userStore.refreshAccessToken();
          processQueue(null, newToken);
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          await userStore.logout();
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        await userStore.logout();
      }

      return Promise.reject(error);
    }

    if (error.response?.status === 401) {
      ElMessage.error("登录已过期，请重新登录");
    } else if (error.response?.status >= 500) {
      ElMessage.error("服务器错误，请稍后重试");
    }

    return Promise.reject(error);
  },
);

export default api;
