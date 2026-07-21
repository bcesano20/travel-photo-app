import {
  ACCESS_TOKEN_KEY,
  API_ENDPOINT_URL,
  API_URL,
  ERROR_MESSAGES,
  REFRESH_TOKEN_KEY,
} from "./constants";
import { AuthLoginInterface } from "./interfaces";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

export async function login(req: AuthLoginInterface): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ req }),
  });

  if (!res.ok) {
    throw new Error(ERROR_MESSAGES.INVALID_CREDENTIALS);
  }

  const data: { access: string; refresh: string } = await res.json();
  setTokens(data.access, data.refresh);
}

export function logout(): void {
  clearTokens();
}

/**
 * Exchanges the refresh token for a new access token. Returns null (and
 * clears storage) if the refresh token is missing, expired, or rejected.
 */
export async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  const res = await fetch(`${API_URL}/${API_ENDPOINT_URL.REFRESH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!res.ok) {
    clearTokens();
    return null;
  }

  const data: { access: string } = await res.json();
  localStorage.setItem(ACCESS_TOKEN_KEY, data.access);
  return data.access;
}
