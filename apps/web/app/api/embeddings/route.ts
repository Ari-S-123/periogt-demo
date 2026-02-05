import { NextRequest, NextResponse } from "next/server";
import { modalFetch, proxyResponse, handleProxyError } from "@/lib/modal-proxy";
import { embeddingRequestSchema } from "@/lib/schemas";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const requestId = crypto.randomUUID();

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      {
        error: { code: "invalid_json", message: "Invalid JSON body" },
        request_id: requestId,
      },
      { status: 400 },
    );
  }

  const parsed = embeddingRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message: "Invalid request",
          details: parsed.error.issues,
        },
        request_id: requestId,
      },
      { status: 422 },
    );
  }

  try {
    const res = await modalFetch("/v1/embeddings", {
      method: "POST",
      body: JSON.stringify(parsed.data),
      headers: { "x-request-id": requestId },
    });
    return proxyResponse(res, requestId);
  } catch (error) {
    return handleProxyError(error, "Embeddings", requestId);
  }
}
