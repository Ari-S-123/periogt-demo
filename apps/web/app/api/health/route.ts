import { modalFetch, proxyResponse, handleProxyError } from "@/lib/modal-proxy";

export async function GET() {
  const requestId = crypto.randomUUID();

  try {
    const res = await modalFetch("/v1/health");
    return proxyResponse(res, requestId);
  } catch (error) {
    return handleProxyError(error, "Health", requestId);
  }
}
