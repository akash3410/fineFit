/**
 * Shared JSON HTTP client for the FineFit storefront API.
 *
 * Security contract (ADR-009):
 *  - Session authentication uses HttpOnly cookies, so every request is sent
 *    with ``credentials: "include"``.
 *  - Unsafe methods (POST/PATCH/PUT/DELETE) must carry the CSRF token in the
 *    ``X-CSRFToken`` header. The token is issued by ``GET /api/v1/auth/csrf/``
 *    and returned in the response body (the ``csrftoken`` cookie itself is
 *    HttpOnly, so JavaScript cannot read it from ``document.cookie``).
 *  - The token is cached in memory. It rotates whenever a session is created
 *    or refreshed by the server, so a single 403 response triggers one token
 *    refresh + retry before the error is surfaced to the UI.
 */

const API_BASE = "/api/v1";

/** Error thrown for any non-2xx API response, carrying the HTTP status. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** HTTP methods that require a CSRF token under Django's session auth. */
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let csrfToken: string | null = null;

/** Drop the cached CSRF token (e.g. after login/logout rotates the session). */
export function resetCsrfToken() {
  csrfToken = null;
}

async function fetchCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;

  const response = await fetch(`${API_BASE}/auth/csrf/`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new ApiError(
      "Could not establish a secure session. Please refresh the page and try again.",
      response.status,
    );
  }

  const data = (await response.json()) as { csrfToken?: string };
  if (!data.csrfToken) {
    throw new ApiError(
      "Could not establish a secure session. Please refresh the page and try again.",
      response.status,
    );
  }
  csrfToken = data.csrfToken;
  return csrfToken;
}

/**
 * Turn an error response into a message a shopper can understand.
 * DRF returns ``{"detail": "..."}`` or ``{"field": ["..."]}``.
 */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object") {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;

      const parts: string[] = [];
      for (const [field, value] of Object.entries(data)) {
        if (field === "cart") continue; // cart snapshot, not an error message
        if (Array.isArray(value)) parts.push(...value.map(String));
        else if (typeof value === "string") parts.push(value);
      }
      if (parts.length > 0) return parts.join(" ");
    }
  } catch {
    // Non-JSON error body (e.g. an HTML debug page): fall through.
  }
  return `Request failed (${response.status}). Please try again.`;
}

/**
 * Fetch options for {@link apiRequest}: a plain object ``body`` is serialized
 * as JSON, everything else is passed through to ``fetch`` unchanged.
 */
export type ApiRequestInit = Omit<RequestInit, "body"> & {
  body?: BodyInit | Record<string, unknown> | null;
};

/**
 * Perform a JSON API request against ``/api/v1``.
 *
 * @param path API path relative to ``/api/v1`` (e.g. ``"/cart/"``).
 * @param init Fetch options; a plain object body is serialized as JSON.
 */
export async function apiRequest<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  return send<T>(path, init, true);
}

async function send<T>(
  path: string,
  init: ApiRequestInit,
  allowCsrfRetry: boolean,
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  let body: BodyInit | null | undefined = init.body as BodyInit | null | undefined;
  const isJsonBody =
    init.body !== undefined &&
    init.body !== null &&
    typeof init.body === "object" &&
    !(init.body instanceof FormData) &&
    !(init.body instanceof URLSearchParams) &&
    !(init.body instanceof Blob);
  if (isJsonBody) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.body);
  }
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (UNSAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", await fetchCsrfToken());
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    body,
    credentials: "include",
  });

  // A rotated CSRF token (or a freshly created guest session) can reject the
  // first write with 403. Refresh the token and retry exactly once.
  if (response.status === 403 && UNSAFE_METHODS.has(method) && allowCsrfRetry) {
    resetCsrfToken();
    return send<T>(path, init, false);
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
