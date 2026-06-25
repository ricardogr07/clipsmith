import type { Clip, Run, RunCreate } from "./types";

// JSON API calls go through the Next.js rewrite proxy (/api/* → FastAPI).
// This avoids CORS and removes the need for NEXT_PUBLIC_API_BASE in the browser.
const PROXY = "/api";

// SSE and file downloads bypass the proxy — they need a persistent/streaming
// connection that the Next.js rewrite layer doesn't guarantee.
const DIRECT = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${PROXY}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  runs: {
    list: () => apiFetch<Run[]>("/runs"),
    get: (id: number) => apiFetch<Run>(`/runs/${id}`),
    create: (body: RunCreate) =>
      apiFetch<Run>("/runs", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: number) => apiFetch<void>(`/runs/${id}`, { method: "DELETE" }),
  },
  clips: {
    list: (runId: number) => apiFetch<Clip[]>(`/runs/${runId}/clips`),
    patch: (id: number, body: { approved?: boolean; title?: string }) =>
      apiFetch<Clip>(`/clips/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  },
  sseUrl: (runId: number) => `${DIRECT}/runs/${runId}/progress`,
  // File downloads go through the proxy (same origin) to avoid mixed-content
  // blocks when the dashboard is served over HTTPS but the API is plain HTTP.
  fileUrl: (runId: number, filename: string) =>
    `${PROXY}/runs/${runId}/clips/file/${encodeURIComponent(filename)}`,
};
