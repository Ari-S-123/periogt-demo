import { modalFetch, proxyResponse, handleProxyError } from "@/lib/modal-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  const requestId = crypto.randomUUID();

  try {
    const res = await modalFetch("/v1/properties");
    return proxyResponse(res, requestId);
  } catch (error) {
    return handleProxyError(error, "Properties", requestId);
  }
}
