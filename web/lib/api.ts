// A thin client over the API. Same origin (/api is proxied to the backend by next.config.ts), cookie session.

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}) },
    ...init,
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? typeof (body as { detail: unknown }).detail === "string"
          ? ((body as { detail: string }).detail as string)
          : JSON.stringify((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
};

/** One Server-Sent Events subscription to a run (docs/web_app_design.md §3). Reconnects are the browser's. */
export function subscribeRun(
  runId: string,
  handlers: { view?: (v: unknown) => void; interrupt?: (v: unknown) => void; final?: (v: unknown) => void; error?: (message: string) => void },
): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`);
  const parse = (e: MessageEvent) => JSON.parse(e.data);
  if (handlers.view) es.addEventListener("view", (e) => handlers.view!(parse(e as MessageEvent)));
  if (handlers.interrupt) es.addEventListener("interrupt", (e) => handlers.interrupt!(parse(e as MessageEvent)));
  es.addEventListener("final", (e) => {
    handlers.final?.(parse(e as MessageEvent));
    es.close();
  });
  es.addEventListener("error", (e) => {
    // a server-sent `event: error` carries data; a transport error does not (the browser retries by itself)
    const data = (e as MessageEvent).data;
    if (data) {
      handlers.error?.(JSON.parse(data).message);
      es.close();
    }
  });
  return () => es.close();
}
