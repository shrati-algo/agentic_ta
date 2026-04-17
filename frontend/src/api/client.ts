import axios from "axios";

/**
 * Shared Axios instance.  The Vite dev server proxies /v1/* to :8000
 * so no explicit baseURL is needed.  In production the backend serves
 * /dist from the same origin, so same-origin requests just work.
 */
export const apiClient = axios.create({
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});
