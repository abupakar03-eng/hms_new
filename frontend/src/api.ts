/**
 * Single place that decides where the API lives and how auth headers are attached.
 *
 * API location:
 *   * Explicit override:  VITE_API_BASE=http://10.0.0.5:8000   (see frontend/.env.example)
 *   * `npm run dev`      -> the standalone backend, normally on port 8000
 *   * production build   -> same origin; the backend serves this bundle, so the app
 *                           works on whatever host/port it was deployed to
 */
import axios from 'axios';

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : window.location.origin);

export const TOKEN_KEY = 'token';
export const REFRESH_KEY = 'refresh_token';

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/** Pull a human-readable message out of an axios error. */
export function errorMessage(error: any, fallback = 'Something went wrong.'): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg || d.type).join(', ');
  return error?.message || fallback;
}

export const api = axios.create();

api.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem(REFRESH_KEY);
      if (refresh) {
        try {
          const res = await axios.post(`${API_BASE}/refresh-token`, { refresh_token: refresh });
          localStorage.setItem(TOKEN_KEY, res.data.access_token);
          original.headers.Authorization = `Bearer ${res.data.access_token}`;
          return api(original);
        } catch {
          clearSession();
        }
      } else {
        clearSession();
      }
    }
    return Promise.reject(error);
  },
);
