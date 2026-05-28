# Governance Boundary: App / Core Separation

This document defines the boundary between Ailuros core and any application (reference
or otherwise) built on top of it. Violations are coupling red lines.

## Core Domain (`src/ailuros/`)

The Ailuros core owns:

- Runtime lifecycle (start, complete, tool wrap).
- Policy evaluation and blocking decisions.
- Run timeline storage and retrieval.
- Path validation.
- CLI commands.
- Policy file validation.
- Adapter contract interfaces.

## Forbidden Coupling

The following are **never** allowed in `src/ailuros/`:

| Category | Examples | Reason |
|---|---|---|
| Browser concepts | Tab, window, navigation, DOM event, content script | Platform-agnostic core |
| Clarify-specific models | CtaField, SidePanelState, ExtensionMessage | Clarify is a reference app, not a core dependency |
| UI state | Active element, hover state, selection range | UI is an application concern |
| Domain-specific entities | Refund request, order, radar track | Domain concepts belong in examples or proof paths |
| HTTP write API | POST /govern, PUT /policy | Platformization is deferred to Phase 5 |
| Auth / sessions | User token, session ID, login state | Out of scope for local runtime kernel |

## Allowed Crossings

Boundary crossings must follow these rules:

1. **Ailuros imports nothing from any reference application.** The dependency graph is
   one-way: apps import Ailuros.
2. **Tool functions** live in example code (`examples/`) or in reference app
   repositories. Ailuros provides the `wrap_tool` gate but does not define the wrapped
   functions.
3. **Policy files** are JSON documents loaded at runtime. They reference tool and action
   names but do not import Python modules from Ailuros core.
4. **Evaluation cases** are JSON documents external to core code.

## Enforcement

- Code review must reject any PR that introduces a reference-app import or
  domain-specific concept into `src/ailuros/`.
- New data types in `src/ailuros/models/` must be application-agnostic.
- If a concept is specific to Clarify, EverRun, or radarCreation, it belongs in that
  project's repository or in `examples/`, never in `src/ailuros/`.
