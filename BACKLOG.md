# 0luka Backlog

Persistent list of high-level objectives and pending tasks for future increments.

## High Priority
- [ ] **Phase 4: Forensics & Live Telemetry**
    - [ ] Replace mock telemetry with real file stream reader in `TelemetryViewer`.
    - [ ] Implement backend `GET /api/v1/telemetry/stream`.
    - [ ] Add log level filtering (INFO/WARN/ERROR) to backend.
- [ ] **Phase 5: Identity & Governance**
    - [ ] Implement browser-based auth (V1.5).
    - [ ] Verify `LDAP`/`OIDC` hooks for enterprise lanes.

## UI/UX Enhancements
- [ ] **Routing**: Implement `Next.js` file-based routing instead of client-side state for Sidebar navigation.
- [ ] **Live Metrics**: Connect "System Pulse" card to real host metrics (CPU/Memory).
- [ ] **Search**: Add full-text search to Telemetry view.

## System Hardening
- [ ] **Audit Trail**: Ensure every write to `interface/inbox` is logged to a secure `audit.log`.
- [ ] **Rate Limiting**: Add rate limiting to `/submit` endpoint.
