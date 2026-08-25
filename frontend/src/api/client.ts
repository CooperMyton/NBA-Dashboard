// Single API client. Every network call goes through apiGet; components never call fetch.

export interface Meta {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface Paged<T> {
  data: T[];
  meta: Meta;
}

export interface Single<T> {
  data: T;
}

interface ApiErrorBody {
  error: { code: string; message: string };
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type QueryParams = Record<string, string | number | boolean | undefined | null>;

export async function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let code = "http_error";
    let message = response.statusText || "Request failed";
    try {
      const body = (await response.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}
