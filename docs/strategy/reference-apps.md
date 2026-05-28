# Reference Applications

Ailuros defines three reference applications that prove the governance-runtime thesis
in different dimensions. None of them is a peer core; all are consumers or proofs.

## Clarify — Evidence-First Governance Reference App

**Role:** First governed reference application. Clarify is a browser extension that
ingests web-browsing evidence and submits it to Ailuros for governance evaluation.

**Status:** Phase 1 — evidence only (timeline ingestion, export, evaluation, regression).

**Key constraint:** Clarify-specific concepts (browser events, CTA fields, side-panel
state, content-script messages) must never appear in `src/ailuros/`. The Clarify
reference architecture is documented in
`docs/architecture/clarify-reference-architecture.md`.

**Repository:** The Clarify implementation lives in its own repository. This Ailuros
repository contains only reference-architecture docs, not Clarify source code.

## EverRun — Automated Agent-Run Platform

**Role:** Proves continuous-run governance, automation, and workflow orchestration on
top of Ailuros.

**Status:** Proof path — design exploration phase.

**Key constraint:** EverRun consumes Ailuros as a library. It does not modify Ailuros
core or introduce core dependencies.

## radarCreation — Vertical Domain Proof

**Role:** Demonstrates Ailuros applicability in a specific vertical domain (radar/defense).

**Status:** Proof path — exploration phase.

**Key constraint:** radarCreation-specific domain concepts must not enter Ailuros core.

## Governance Model

```
┌─────────────────────────────────────────────────┐
│              Ailuros (Core Governance Runtime)   │
│  Policy gate · Timeline · Path validation · CLI  │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │
       ▼          ▼          ▼
   Clarify    EverRun   radarCreation
  (ref app)  (proof)    (proof)
```

All three reference applications sit *above* Ailuros. They consume its governance
services but never redefine them. Ailuros strategy, architecture, and roadmap are
defined in this repository and apply to the entire product line.
