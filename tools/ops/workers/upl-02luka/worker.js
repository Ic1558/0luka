var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// worker.js
var worker_default = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (path === "/health") {
      return new Response(JSON.stringify({
        status: "healthy",
        worker: "upl-worker",
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
        version: "1.0.0"
      }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    if (path === "/upload" && request.method === "POST") {
      return handleUpload(request, env);
    }
    return new Response(JSON.stringify({
      error: "Not Found",
      worker: "upl-worker"
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }
};
async function handleUpload(request, env) {
  try {
    const authHeader = request.headers.get("x-gg-auth");
    if (!authHeader) {
      return new Response(JSON.stringify({
        error: "Authentication required",
        code: "AUTH_MISSING"
      }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }
    const isValidAuth = await verifyHMAC(request, authHeader, env.SHARED_SECRET);
    if (!isValidAuth) {
      return new Response(JSON.stringify({
        error: "Invalid authentication",
        code: "AUTH_INVALID"
      }), {
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }
    const formData = await request.formData();
    const file = formData.get("file");
    const metadata = formData.get("metadata");
    if (!file) {
      return new Response(JSON.stringify({
        error: "No file provided",
        code: "FILE_MISSING"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }
    const uploadId = generateUploadId();
    const result = {
      uploadId,
      filename: file.name,
      size: file.size,
      type: file.type,
      timestamp: (/* @__PURE__ */ new Date()).toISOString(),
      status: "uploaded"
    };
    return new Response(JSON.stringify({
      success: true,
      data: result
    }), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Upload failed",
      code: "UPLOAD_ERROR",
      details: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handleUpload, "handleUpload");
async function verifyHMAC(request, authHeader, secret) {
  try {
    const body = await request.clone().text();
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"]
    );
    const signature = new Uint8Array(
      authHeader.split("").map((c) => c.charCodeAt(0))
    );
    return await crypto.subtle.verify(
      "HMAC",
      key,
      signature,
      encoder.encode(body)
    );
  } catch {
    return false;
  }
}
__name(verifyHMAC, "verifyHMAC");
function generateUploadId() {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `upl_${timestamp}_${random}`;
}
__name(generateUploadId, "generateUploadId");
export {
  worker_default as default
};
//# sourceMappingURL=worker.js.map