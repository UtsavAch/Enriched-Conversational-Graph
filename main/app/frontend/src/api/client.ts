/**
 * The single place a network request is made.
 *
 * Everything above this file works with typed functions, never with URLs or
 * `fetch`. That keeps error handling, JSON parsing and the base path in one
 * place instead of scattered across components.
 */

/**
 * Relative by default. In dev, Vite proxies /api to the FastAPI server; in
 * production FastAPI serves the bundle itself. Either way '/api/...' resolves,
 * so no component ever needs to know which mode it is running in.
 */
const BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** True when the server rejected the action rather than failing at it. */
  get isForbidden() { return this.status === 403; }
  get isNotFound() { return this.status === 404; }
  /** True when the server could not be reached at all. */
  get isNetworkError() { return this.status === 0; }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (cause) {
    // A failed fetch means the server is not running or is unreachable.
    // Distinguishing this from an HTTP error matters: the fix is completely
    // different, and the UI says so.
    throw new ApiError(0, 'Cannot reach the server', String(cause));
  }

  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => '');
    }
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const http = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),

  /** Multipart upload. Deliberately does not set Content-Type — the browser
   *  must add the multipart boundary itself. */
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),

  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
