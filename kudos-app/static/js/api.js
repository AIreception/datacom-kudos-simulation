/**
 * Small API client for the Kudos demo.
 *
 * The CSRF token is kept in memory only. Every unsafe request automatically
 * includes it, and the server rejects the request when it is missing or stale.
 */

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

let csrfToken = null;

export class ApiError extends Error {
  constructor(status, code, message, fields = {}, requestId = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields || {};
    this.requestId = requestId;
  }
}

export function setCsrfToken(token) {
  csrfToken = typeof token === "string" && token ? token : null;
}

export function getCsrfToken() {
  return csrfToken;
}

function buildQuery(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function apiFetch(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  let body = options.body;

  if (body !== undefined && body !== null && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  if (!SAFE_METHODS.has(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  let response;
  try {
    response = await fetch(path, {
      ...options,
      method,
      headers,
      body,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Could not reach the server. Check that the app is running and try again.",
    );
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
  }

  if (!response.ok) {
    const detail = data && data.error ? data.error : {};
    throw new ApiError(
      response.status,
      detail.code || "HTTP_ERROR",
      detail.message || `Request failed with status ${response.status}.`,
      detail.fields || {},
      detail.requestId || response.headers.get("X-Request-Id"),
    );
  }

  return data;
}

export const api = {
  getCsrf() {
    return apiFetch("/api/csrf");
  },

  getDemoUsers() {
    return apiFetch("/api/demo/users");
  },

  login(userId) {
    return apiFetch("/api/demo/session", {
      method: "POST",
      body: { userId },
    });
  },

  logout() {
    return apiFetch("/api/demo/session", { method: "DELETE" });
  },

  me() {
    return apiFetch("/api/me");
  },

  users() {
    return apiFetch("/api/users");
  },

  kudos({ limit = 20, offset = 0 } = {}) {
    return apiFetch(`/api/kudos${buildQuery({ limit, offset })}`);
  },

  createKudos({ recipientId, message }) {
    return apiFetch("/api/kudos", {
      method: "POST",
      body: { recipientId, message },
    });
  },

  adminKudos({ limit = 20, offset = 0, visibility = "all" } = {}) {
    return apiFetch(
      `/api/admin/kudos${buildQuery({ limit, offset, visibility })}`,
    );
  },

  hideKudos(id) {
    return apiFetch(`/api/admin/kudos/${id}/hide`, { method: "POST" });
  },

  restoreKudos(id) {
    return apiFetch(`/api/admin/kudos/${id}/restore`, { method: "POST" });
  },

  deleteKudos(id) {
    return apiFetch(`/api/admin/kudos/${id}`, { method: "DELETE" });
  },
};
