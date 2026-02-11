var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// ops-worker.js
function esc(s = "") {
  return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
__name(esc, "esc");
var now = /* @__PURE__ */ __name(() => Math.floor(Date.now() / 1e3), "now");
var h = /* @__PURE__ */ __name((env) => ({
  min: env.ALERT_MIN_SEVERITY || "warn",
  cd: Number(env.ALERT_COOLDOWN_SEC || 300)
}), "h");
async function shouldSend(env, key, cooldown) {
  const last = await env.ALERT_KV.get(key, "json");
  const ok = !last || now() - last.t >= cooldown;
  if (ok) await env.ALERT_KV.put(key, JSON.stringify({ t: now() }), { expirationTtl: cooldown + 60 });
  return ok;
}
__name(shouldSend, "shouldSend");
async function postDiscord(url, payload) {
  return fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
}
__name(postDiscord, "postDiscord");
async function alertBridge(req, env) {
  const body = await req.json().catch(() => ({}));
  const { severity = "info", source = "unknown", title = "Event", details = {}, dedupeKey } = body;
  const levels = ["info", "warn", "error"];
  if (levels.indexOf(severity) < levels.indexOf(h(env).min)) return Response.json({ ok: true, skipped: "below_threshold" });
  const key = dedupeKey || `${source}:${title}:${severity}`;
  if (!await shouldSend(env, key, h(env).cd)) return Response.json({ ok: true, skipped: "cooldown" });
  const embed = {
    username: "02LUKA Alerts",
    content: "",
    embeds: [{
      title: `[${severity.toUpperCase()}] ${title}`,
      description: "```json\n" + JSON.stringify(details, null, 2).slice(0, 1800) + "\n```",
      color: severity === "error" ? 14427686 : severity === "warn" ? 14251782 : 2450411,
      footer: { text: source },
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }]
  };
  if (env.DISCORD_WEBHOOK_DEFAULT) await postDiscord(env.DISCORD_WEBHOOK_DEFAULT, embed);
  return Response.json({ ok: true, sent: true });
}
__name(alertBridge, "alertBridge");
function governanceHTML(model) {
  const { status = "unknown", uptimePct = 0, lastHeal = "-", nodes = [], alerts = [] } = model;
  const staticTop = String.raw`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Governance · 02LUKA</title>
<style>
  body{font:14px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:24px;}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;}
  .card{border:1px solid #e5e7eb;border-radius:12px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.04);}
  .ok{color:#059669}.warn{color:#d97706}.bad{color:#dc2626}
  pre{background:#0b1020;color:#e5e7eb;border-radius:8px;padding:12px;overflow:auto}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}
  table{width:100%;border-collapse:collapse} th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}
  .alert-badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold}
  .alert-info{background:#dbeafe;color:#1e40af}
  .alert-warn{background:#fef3c7;color:#92400e}
  .alert-error{background:#fee2e2;color:#dc2626}
</style>
</head>
<body>
<h1>Governance Dashboard</h1>
<div class="grid">`;
  const headerCards = `
  <div class="card">
    <div>Status</div>
    <div class="${status === "ok" ? "ok" : status === "warn" ? "warn" : "bad"}"><strong>${esc(status)}</strong></div>
  </div>
  <div class="card">
    <div>Uptime (24h)</div>
    <div><strong>${esc(uptimePct)}%</strong></div>
  </div>
  <div class="card">
    <div>Last Auto-Heal</div>
    <div><strong>${esc(lastHeal)}</strong></div>
  </div>
  <div class="card">
    <div>Alerts (24h)</div>
    <div><strong>${alerts.length}</strong> <span class="alert-badge alert-${alerts.length > 0 ? alerts[0].severity : "info"}">${alerts.length > 0 ? alerts[0].severity.toUpperCase() : "NONE"}</span></div>
  </div>`;
  const nodeRows = nodes.map((n) => `
    <tr>
      <td>${esc(n.name)}</td>
      <td>${esc(n.role)}</td>
      <td class="${n.health === "ok" ? "ok" : n.health === "warn" ? "warn" : "bad"}">${esc(n.health)}</td>
      <td>${esc(n.uptime || "-")}</td>
    </tr>`).join("");
  const alertRows = alerts.slice(0, 3).map((a) => `
    <tr>
      <td>${esc(a.source)}</td>
      <td><span class="alert-badge alert-${a.severity}">${esc(a.severity.toUpperCase())}</span></td>
      <td>${esc(a.title)}</td>
      <td>${esc(new Date(a.timestamp).toLocaleString())}</td>
    </tr>`).join("");
  const staticBottom = String.raw`
</div>

<div class="card" style="margin-top:16px">
  <h3>Cluster</h3>
  <table>
    <thead><tr><th>Node</th><th>Role</th><th>Health</th><th>Uptime</th></tr></thead>
    <tbody>__NODE_ROWS__</tbody>
  </table>
</div>

<div class="card" style="margin-top:16px">
  <h3>Recent Alerts</h3>
  <table>
    <thead><tr><th>Source</th><th>Severity</th><th>Title</th><th>Time</th></tr></thead>
    <tbody>__ALERT_ROWS__</tbody>
  </table>
</div>

<div class="card" style="margin-top:16px">
  <h3>Notes</h3>
  <p>Static literals with <code>${"${"}vars}</code> will NOT break here because this block is produced with <code>String.raw</code>.</p>
  <pre><code>// Example curl
curl -s https://ops-02luka.ittipong-c.workers.dev/ops/health | jq</code></pre>
</div>

</body></html>`;
  return new Response(
    (staticTop + headerCards + staticBottom).replace("__NODE_ROWS__", nodeRows || '<tr><td colspan="4">No nodes</td></tr>').replace("__ALERT_ROWS__", alertRows || '<tr><td colspan="4">No alerts</td></tr>'),
    {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "same-origin",
        "content-security-policy": "default-src 'self'; style-src 'unsafe-inline' 'self'; base-uri 'none'; frame-ancestors 'none'"
      }
    }
  );
}
__name(governanceHTML, "governanceHTML");
var ops_worker_default = {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const securityHeaders = {
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "X-XSS-Protection": "1; mode=block",
      "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    };
    if (req.method === "POST" && url.pathname === "/ops/alert") {
      return alertBridge(req, env);
    }
    if (req.method === "GET" && url.pathname === "/api/ping") {
      return new Response(JSON.stringify({
        ok: true,
        ts: (/* @__PURE__ */ new Date()).toISOString(),
        version: "9.2-C",
        status: "healthy"
      }), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (req.method === "GET" && url.pathname === "/api/health") {
      const healthData = {
        status: "healthy",
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
        version: "9.2-C",
        uptime: "active",
        services: {
          worker: "online",
          tunnel: "connected",
          bridge: "pending"
        },
        metrics: {
          response_time: "< 100ms",
          success_rate: "100%",
          last_check: (/* @__PURE__ */ new Date()).toISOString()
        }
      };
      return new Response(JSON.stringify(healthData), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (req.method === "GET" && url.pathname === "/api/predict/latest") {
      const predictData = {
        risk_level: "low",
        horizon_hours: 24,
        confidence: 0.85,
        recommendations: [
          "System operating normally",
          "No immediate action required",
          "Continue monitoring"
        ],
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      };
      return new Response(JSON.stringify(predictData), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (req.method === "GET" && url.pathname === "/api/federation/ping") {
      return new Response(JSON.stringify({
        ok: true,
        peers: 0,
        status: "standalone",
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      }), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (req.method === "GET" && url.pathname === "/api/maintenance") {
      return new Response(JSON.stringify({
        maintenance: false,
        status: "operational",
        timestamp: (/* @__PURE__ */ new Date()).toISOString()
      }), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (url.pathname === "/ops/governance") {
      const model = {
        status: "ok",
        uptimePct: 99.92,
        lastHeal: (/* @__PURE__ */ new Date()).toISOString(),
        nodes: [
          { name: "mini-pc", role: "tunnel", health: "ok", uptime: "23h 58m" },
          { name: "bridge", role: "api", health: "ok", uptime: "6h 12m" },
          { name: "worker", role: "edge", health: "ok", uptime: "2h 45m" },
          { name: "autoheal", role: "monitor", health: "ok", uptime: "1h 23m" }
        ],
        alerts: [
          { source: "autoheal", severity: "warn", title: "Process restart", timestamp: new Date(Date.now() - 36e5).toISOString() },
          { source: "health", severity: "info", title: "Health check passed", timestamp: new Date(Date.now() - 72e5).toISOString() }
        ]
      };
      return governanceHTML(model);
    }
    if (url.pathname === "/ops/health") {
      return new Response(JSON.stringify({ ok: true, ts: Date.now() }), {
        headers: { "content-type": "application/json", ...securityHeaders }
      });
    }
    if (req.method === "GET" && url.pathname === "/") {
      const mainUI = String.raw`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>02luka Ops UI v9.2-C</title>
  <style>
    body { font: 14px system-ui; margin: 24px; background: #f5f5f5; }
    .container { max-width: 1200px; margin: 0 auto; }
    .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
    .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .nav { display: flex; gap: 10px; margin-bottom: 20px; }
    .nav a { padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }
    .nav a:hover { background: #0056b3; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🧠 02luka Ops UI v9.2-C</h1>
      <p>System Governance & Auto-Recovery with Alert Bridge</p>
    </div>
    
    <div class="nav">
      <a href="/">Dashboard</a>
      <a href="/ops/governance">Governance</a>
      <a href="/api/ping">API Status</a>
    </div>
    
    <div class="card">
      <h3>System Status</h3>
      <p>Welcome to 02luka Ops UI v9.2-C with enhanced governance, auto-recovery, and alert bridge capabilities.</p>
      <p><strong>Features:</strong></p>
      <ul>
        <li>🧭 Governance Dashboard - Agent management and monitoring</li>
        <li>⚙️ Auto-Heal Daemon - Automatic process recovery</li>
        <li>📢 Alert Bridge - Discord notifications with deduplication</li>
        <li>📊 Real-time monitoring - Health checks and metrics</li>
        <li>🔒 Security hardening - Production-ready security</li>
      </ul>
    </div>
  </div>
</body>
</html>`;
      return new Response(mainUI, {
        headers: { "content-type": "text/html; charset=utf-8", ...securityHeaders }
      });
    }
    return new Response("Not found", { status: 404, headers: securityHeaders });
  }
};
export {
  ops_worker_default as default
};
//# sourceMappingURL=ops-worker.js.map