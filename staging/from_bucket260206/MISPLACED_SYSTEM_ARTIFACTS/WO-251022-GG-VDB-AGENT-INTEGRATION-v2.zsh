#!/usr/bin/env zsh
set -euo pipefail
WO_ID="WO-251022-GG-VDB-AGENT-INTEGRATION-v2"
INBOX="$HOME/02luka/bridge/inbox/CLC"; LOGDIR="$HOME/02luka/logs/wo_drop_history"
TMP="$(mktemp -d)"; mkdir -p "$INBOX" "$LOGDIR"

cat > "$TMP/$WO_ID.md" <<'MD'
# WO: Agent Integration (MCP + Redis/Shell) + Perf Logging + Tests
- **ID:** WO-251022-GG-VDB-AGENT-INTEGRATION-v2
- **Goal:** Expose `knowledge/index.cjs` to all agents (MCP first, Redis fallback), add perf logging, add basic integration tests.

## Tasks
1) MCP tool `knowledge.hybrid_search` (params: query, top_k=8, mode="hybrid"|"verify"|"fts", print_snippet=false) → JSON result schema.
2) Safe shell wrapper `tools/hybrid_search.sh` (quotes + length cap 2k).
3) **Perf logging**: add `knowledge/util/perf_log.cjs` and call it from `--verify` path in `knowledge/index.cjs`.
```js
// knowledge/util/perf_log.cjs
import fs from 'fs';
export function logQuery(entry){
  const line = JSON.stringify({ ts:new Date().toISOString(), ...entry })+'\n';
  fs.appendFileSync('g/reports/query_perf.jsonl', line);
}
```
(From index.cjs --verify after timings:)
```js
logQuery({ query:q.slice(0,100), mode:'verify', timings, resultCount:results.length });
```
4) Integration tests `knowledge/test/integration_test.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
node knowledge/index.cjs --verify "phase 7.2" --k=5 >/dev/null
tools/hybrid_search.sh "token savings" 8 hybrid >/dev/null
echo '{"tool":"knowledge.hybrid_search","params":{"query":"deployment schema"}}' > /tmp/mcp_req.json
echo "OK"
```
5) Docs update in `docs/AGENT_INTEGRATION_HYBRID_ENGINE.md`.

## Acceptance
- MCP tool returns JSON for sample query.
- Redis shell wrapper runs safely with quotes.
- `g/reports/query_perf.jsonl` appends on `--verify`.
- `integration_test.sh` prints OK.

MD

DST="$INBOX/$WO_ID.md"; mv "$TMP/$WO_ID.md" "$DST"
cp -a "$DST" "$LOGDIR/${WO_ID}_$(date +%Y%m%d_%H%M%S).md"
echo "✅ Dropped $WO_ID to $DST"
