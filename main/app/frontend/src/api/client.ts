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
const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the server rejected the action rather than failing at it. */
  get isForbidden() {
    return this.status === 403;
  }
  get isNotFound() {
    return this.status === 404;
  }
  /** True when the server could not be reached at all. */
  get isNetworkError() {
    return this.status === 0;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (cause) {
    // A failed fetch means the server is not running or is unreachable.
    // Distinguishing this from an HTTP error matters: the fix is completely
    // different, and the UI says so.
    throw new ApiError(0, "Cannot reach the server", String(cause));
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail =
        typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => "");
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),

  /** Multipart upload. Deliberately does not set Content-Type — the browser
   *  must add the multipart boundary itself. */
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),

  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * Minimal POST-based Server-Sent Events reader.
 *
 * Native `EventSource` only supports GET, and a chat question does not
 * belong in a query string — so this parses the (simple) SSE wire format by
 * hand over a plain `fetch()` stream, rather than pulling in a library for
 * something this small. One frame is `event: <name>\ndata: <json>\n\n`;
 * frames are separated by a blank line, which is all this needs to handle.
 */
export async function* streamSSE(
  path: string,
  body: unknown,
): AsyncGenerator<SSEEvent> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError(0, "Cannot reach the server", String(cause));
  }

  if (!res.ok) {
    let detail = "";
    try {
      const errBody = await res.json();
      detail =
        typeof errBody?.detail === "string"
          ? errBody.detail
          : JSON.stringify(errBody);
    } catch {
      detail = await res.text().catch(() => "");
    }
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, detail);
  }
  if (!res.body) {
    throw new ApiError(
      0,
      "Streaming not supported",
      "Response had no readable body",
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) yield { event, data: dataLines.join("\n") };
    }
  }
}
