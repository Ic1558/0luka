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
        worker: "idx-worker",
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
        version: "1.0.0",
        policies: "active"
      }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    if (path === "/search" && request.method === "GET") {
      return handleSearch(request, env);
    }
    if (path === "/index" && request.method === "POST") {
      return handleIndex(request, env);
    }
    if (path === "/policy" && request.method === "POST") {
      return handlePolicyCheck(request, env);
    }
    return new Response(JSON.stringify({
      error: "Not Found",
      worker: "idx-worker"
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }
};
async function handleSearch(request, env) {
  try {
    const url = new URL(request.url);
    const query = url.searchParams.get("q");
    const limit = parseInt(url.searchParams.get("limit") || "10");
    const offset = parseInt(url.searchParams.get("offset") || "0");
    if (!query) {
      return new Response(JSON.stringify({
        error: "Query parameter required",
        code: "QUERY_MISSING"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }
    const policyResult = await checkSearchPolicy(query, env);
    if (!policyResult.allowed) {
      return new Response(JSON.stringify({
        error: "Search not allowed by policy",
        code: "POLICY_DENIED",
        reason: policyResult.reason
      }), {
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }
    const results = await searchIndex(query, limit, offset, env);
    return new Response(JSON.stringify({
      success: true,
      query,
      count: results.length,
      limit,
      offset,
      data: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Search failed",
      code: "SEARCH_ERROR",
      details: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handleSearch, "handleSearch");
async function handleIndex(request, env) {
  try {
    const data = await request.json();
    const policyResult = await checkIndexPolicy(data, env);
    if (!policyResult.allowed) {
      return new Response(JSON.stringify({
        error: "Indexing not allowed by policy",
        code: "POLICY_DENIED",
        reason: policyResult.reason
      }), {
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }
    const indexResult = await addToIndex(data, env);
    return new Response(JSON.stringify({
      success: true,
      indexed: true,
      indexId: indexResult.id,
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Indexing failed",
      code: "INDEX_ERROR",
      details: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handleIndex, "handleIndex");
async function handlePolicyCheck(request, env) {
  try {
    const data = await request.json();
    const { action, resource, context } = data;
    const result = await evaluatePolicy(action, resource, context, env);
    return new Response(JSON.stringify({
      success: true,
      allowed: result.allowed,
      reason: result.reason,
      policies: result.appliedPolicies
    }), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Policy check failed",
      code: "POLICY_ERROR",
      details: error.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
__name(handlePolicyCheck, "handlePolicyCheck");
async function checkSearchPolicy(query, env) {
  const blockedTerms = ["admin", "password", "secret"];
  const hasBlockedTerm = blockedTerms.some(
    (term) => query.toLowerCase().includes(term)
  );
  return {
    allowed: !hasBlockedTerm,
    reason: hasBlockedTerm ? "Query contains blocked terms" : "Allowed"
  };
}
__name(checkSearchPolicy, "checkSearchPolicy");
async function checkIndexPolicy(data, env) {
  const maxSize = 10 * 1024 * 1024;
  const dataSize = JSON.stringify(data).length;
  return {
    allowed: dataSize <= maxSize,
    reason: dataSize > maxSize ? "Data too large" : "Allowed"
  };
}
__name(checkIndexPolicy, "checkIndexPolicy");
async function evaluatePolicy(action, resource, context, env) {
  const allowedActions = ["read", "search", "index"];
  const allowed = allowedActions.includes(action);
  return {
    allowed,
    reason: allowed ? "Action permitted" : "Action not in allowed list",
    appliedPolicies: ["default-policy"]
  };
}
__name(evaluatePolicy, "evaluatePolicy");
async function searchIndex(query, limit, offset, env) {
  return [
    {
      id: "doc_001",
      title: `Result for "${query}"`,
      score: 0.95,
      snippet: `This is a search result for ${query}...`,
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }
  ];
}
__name(searchIndex, "searchIndex");
async function addToIndex(data, env) {
  const indexId = `idx_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
  return {
    id: indexId,
    status: "indexed"
  };
}
__name(addToIndex, "addToIndex");
export {
  worker_default as default
};
//# sourceMappingURL=worker.js.map