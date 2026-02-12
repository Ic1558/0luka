# Constitutional Decree — Core Is Law

This decree is enforceable through `core/governance/separation_of_powers.yaml`.

## Article I — Constitutional Supremacy
`core/` is the constitutional ring (R3). Governance contracts, ABI, ontology, and phase registry are the legal source of truth.

## Article II — Separation Of Powers
`core_brain/` operates as interpretation/execution culture (R2) and may extend constitutional law, but may not replace constitutional sources.

## Article III — Runtime Enforcement
`tools/ops/` (R1) enforces governance rules and validates compliance. Runtime validators must fail closed on contract violations.

## Article IV — Evidence Discipline
`observability/` (R0) is append-oriented evidence storage. Evidence is auditable output, not legal source of truth.

## Article V — Canonical Source Control
Canonical governance files in `core/governance/` must not be duplicated into `core_brain/governance/` where `no_copy_in` is declared by constitutional contract.
