# OPAL Kernel Documentation

**Authoritative (The Law):**
- [👑 KERNEL_CONSTITUTION.md](core/docs/KERNEL_CONSTITUTION.md)

**Explanatory (The Model):**
- [ARCHITECTURE_MODEL.md](core/docs/architecture_model.md)

**Historical (The Lessons):**
- [postmortem_v1.3.0.md](docs/reports/postmortem_v1.3.0.md)

**Philosophy (The Spirit):**
- [kernel_manifesto.md](docs/manifests/kernel_manifesto.md)

**Intent (The Future):**
- [ROADMAP_v2.md](ROADMAP_v2.md)

## AG-17 Final Closure

- AG-17A = COMPLETE
- AG-17B = COMPLETE
- AG-17C = COMPLETE
- AG-17D = CLOSED (Decision B semantics)
- AG-17 line = CLOSED

AG-17 closed by semantic clarification, not runtime redesign. The integrity model now distinguishes embedded envelope integrity (`execution_envelope.provenance.outputs_sha256`) from final artifact integrity (`provenance.hashes.outputs_sha256`): both are valid integrity signals in different scopes, and equality is not required.

Architecture detail is recorded in `docs/architecture/0LUKA_CAPABILITY_MAP.md` under `AG-17 closeout verification` and `ExecutionEnvelope Integrity Model (Post-AG-17)`. Runtime closeout evidence is preserved in `evidence/ag17/`, including `evidence/ag17/README.md`, `evidence/ag17/ag17_closeout_summary.json`, and `evidence/ag17/ag17_closeout_runtime_artifact.json`.

ExecutionEnvelope is now a stable, documented integrity layer, so AG-17 no longer blocks forward architecture work. Future provenance hardening is optional and separate from AG-17.
# Post-merge verification trigger
