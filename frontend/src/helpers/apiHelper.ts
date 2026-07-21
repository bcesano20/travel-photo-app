import { API_URL } from "./constants";
import { clearTokens, getAccessToken, refreshAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function doFetch(
  path: string,
  token: string | null,
  options: RequestInit,
): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const accessToken = getAccessToken();
  let res = await doFetch(path, accessToken, options);

  if (res.status === 401 && accessToken) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetch(path, newToken, options);
    } else {
      clearTokens();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as Record<string, unknown>);
    const message =
      typeof body.detail === "string" ? body.detail : `Request failed with status ${res.status}`;
    throw new ApiError(res.status, message);
  }

  return res;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, data?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });
  return res.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, data?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "PATCH",
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });
  return res.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  await apiFetch(path, { method: "DELETE" });
}
