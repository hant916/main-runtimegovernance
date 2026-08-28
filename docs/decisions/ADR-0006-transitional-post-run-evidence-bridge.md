# ADR-0006: Transitional Post-Run Evidence Bridge

**Status:** Accepted

**Date:** 2026-08-28

## Context

The Runtime Evidence Package v1 is the proven, source-neutral path for moving a
completed runtime's evidence into Ailuros. EverRun/Ailuros dogfood uses it for
post-run validation, deterministic projection, and governance diagnosis.

That demonstrated role is valuable, but it is narrower than a durable product
commitment to own a universal evidence interchange or attestation standard. The
package arrives after execution and is non-enforcing: it cannot itself provide
the pre-action evidence or intervention point required for runtime governance
control.

## Decision

Treat Evidence Package v1 as the current **transitional post-run ingestion
bridge**.

- It remains accepted, supported, source-neutral, and compatible with existing
  producers, readers, writers, validators, and CLI commands.
- It remains a useful dogfood and migration scaffold for completed-run evidence.
- Its wire shape, required fields, validation rules, naming rules, provenance,
  and deterministic identity semantics are unchanged by this decision.
- "Canonical" and "portable", where used, describe the current internal
  Ailuros bridge contract only. They do not claim ownership of an industry
  interchange or attestation standard.
- Package integrity, provenance, or portability may inform an assessment, but
  never establish authority, permission, or governance approval by themselves.

The target integration path is **runtime-native governance evidence flow**:
equivalent evidence is available directly at a runtime governance boundary in
time for deterministic policy evaluation and a justified intervention.

## Retirement Condition

The bridge is not immediately deprecated. It may be retired only when both of
the following are true:

1. Equivalent evidence is proven available and consumed directly at the relevant
   runtime governance boundaries; and
2. Existing producer and reader compatibility needs for the post-run bridge have
   ended or have an explicitly supported replacement.

Once those conditions hold, new product work must not depend on the bridge.
Until then, it remains the live post-run compatibility path.

## Consequences

- No TRACE, SCITT, cryptographic-attestation, signature-verification, exporter,
  verifier, registry, or generic adapter framework is introduced by this
  decision.
- External attestation or interchange standards are outside this contract's
  ownership. A concrete producer/consumer need may justify a future scoped
  integration decision, but market adjacency alone does not.
- Post-run findings remain evidence and diagnostics; they do not automatically
  become runtime control gates.
