/**
 * Udhaar Ledger API client.
 * Authentication is handled by Clerk: every request carries a short-lived Clerk session JWT.
 * <ClerkTokenBridge/> registers Clerk's getToken() here once Clerk has loaded.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

type TokenGetter = () => Promise<string | null>;
let tokenGetter: TokenGetter | null = null;
let signOutHandler: (() => Promise<void> | void) | null = null;
let readyResolve: (() => void) | null = null;
const ready = new Promise<void>((r) => (readyResolve = r));

export function registerAuth(getter: TokenGetter, signOut: () => Promise<void> | void) {
  tokenGetter = getter;
  signOutHandler = signOut;
  readyResolve?.();
}

export async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  await Promise.race([ready, new Promise((r) => setTimeout(r, 4000))]);
  return tokenGetter ? tokenGetter() : null;
}

export async function logout(): Promise<void> {
  if (signOutHandler) await signOutHandler();
  if (typeof window !== "undefined") window.location.href = "/login";
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function authedFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = `/login?redirect_url=${encodeURIComponent(window.location.pathname)}`;
    throw new ApiError(401, "Your session has ended. Please sign in again.");
  }
  if (!response.ok) {
    const text = await response.text();
    let detail = response.statusText;
    try {
      const parsed = JSON.parse(text);
      detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail ?? parsed);
    } catch {
      detail = text || detail;
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

/** JSON request. Sets Content-Type for string bodies; leaves FormData alone. */
export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await authedFetch(endpoint, { ...options, headers });
  return res.json() as Promise<T>;
}

/** Authenticated file download (plain <a href> links cannot carry the bearer token). */
export async function downloadFile(endpoint: string, fallbackName: string): Promise<void> {
  const res = await authedFetch(endpoint);
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function formatINR(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null) return "₹0";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return "₹0";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(num);
}

/** Compact INR: ₹4.2 Cr, ₹38.5 L, ₹12.4 K */
export function formatINRCompact(amount: number | string | undefined | null): string {
  const n = typeof amount === "string" ? parseFloat(amount) : amount ?? 0;
  if (!n || isNaN(n)) return "₹0";
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  if (abs >= 1e3) return `₹${(n / 1e3).toFixed(1)} K`;
  return `₹${Math.round(n)}`;
}

export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
