import { NextResponse } from "next/server";
import { getServerEnv } from "./env";

/**
 * Forward a request to the Modal PerioGT backend with authentication.
 * Used by all BFF route handlers.
 */
export async function modalFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const env = getServerEnv();
  const url = `${env.MODAL_PERIOGT_URL}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), 60_000);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "Modal-Key": env.MODAL_KEY,
        "Modal-Secret": env.MODAL_SECRET,
        ...(options.headers as Record<string, string>),
      },
    });
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Safely parse a Modal backend response as JSON.
 * Returns a NextResponse with the parsed data, or an error response
 * if the backend returned non-JSON.
 */
export async function proxyResponse(
  res: Response,
  requestId: string,
): Promise<NextResponse> {
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    const text = await res.text().catch(() => "");
    console.error("Backend returned non-JSON response:", res.status, text.slice(0, 200));
    return NextResponse.json(
      {
        error: {
          code: "backend_error",
          message: "Backend returned an invalid response",
        },
        request_id: requestId,
      },
      { status: 502 },
    );
  }

  return NextResponse.json(data, { status: res.status });
}

/**
 * Handle proxy errors (timeout, network failure) consistently.
 */
export function handleProxyError(
  error: unknown,
  label: string,
  requestId: string,
): NextResponse {
  if (error instanceof DOMException && error.name === "AbortError") {
    return NextResponse.json(
      { error: { code: "timeout", message: "Backend request timed out" }, request_id: requestId },
      { status: 504 },
    );
  }
  console.error(`${label} proxy error:`, error);
  return NextResponse.json(
    { error: { code: "proxy_error", message: "Failed to reach backend" }, request_id: requestId },
    { status: 502 },
  );
}
