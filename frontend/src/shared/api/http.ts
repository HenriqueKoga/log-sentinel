import axios from "axios";
import { clearTokens, getAccessToken, getRefreshToken, setTokens, type TokenPair } from "../auth/storage";

const baseURL = import.meta.env.DEV
  ? ""
  : ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "");

export const http = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

const refreshClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = refreshClient
    .post<{ access_token: string; refresh_token: string; token_type: string }>(
      "/api/v1/auth/refresh",
      { refresh_token: refreshToken },
    )
    .then((resp) => {
      const data = resp.data;
      const pair: TokenPair = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      };
      setTokens(pair);
      return pair.accessToken;
    })
    .catch(() => null)
    .finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });

  return refreshPromise;
}

http.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error?.response?.status;
    const originalRequest = error.config ?? {};

    if (status === 401 && !originalRequest._retry) {
      const newAccessToken = await refreshAccessToken();
      if (newAccessToken) {
        originalRequest._retry = true;
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return http(originalRequest);
      }
    }

    if (status === 401) {
      clearTokens();
      if (typeof window !== "undefined") window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);

