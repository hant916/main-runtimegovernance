# Ailuros Current Product State

This file records Ailuros product state only. It does not use EverRun runtime traces, planner state, hardening packs, or execution history as product truth.

## Runtime-Kernel Progress

T001-T010 in `sdd/everrun-tasks.md` are the runtime-kernel progress source of truth. Completed tasks require local implemented-file evidence and reproducible validation commands recorded in that file.

Current mapped implementation surface:

- T001 package bootstrap, CLI entrypoint, and refund example: implemented in `pyproject.toml`, `src/ailuros/__init__.py`, `src/ailuros/__main__.py`, `src/ailuros/cli.py`, `tests/test_smoke.py`, and `examples/refund_agent/main.py`.
- T002 runtime data models: implemented in `src/ailuros/models/` with coverage in `tests/test_models.py`.
- T003 SQLite append-only storage: implemented in `src/ailuros/storage/sqlite_storage.py`, `src/ailuros/storage/migrations/001_initial.sql`, and `tests/test_sqlite_storage.py`.
- T004 runtime lifecycle APIs: implemented in `src/ailuros/runtime/`, compatibility exports, and `tests/test_runtime_lifecycle.py`.
- T005 run inspection CLI: implemented in `src/ailuros/cli.py`, `src/ailuros/cli_run.py`, and `tests/test_cli_run.py`.
- T006 policy loader and validation CLI: implemented in `src/ailuros/policy/loader.py`, `src/ailuros/policy/validator.py`, `src/ailuros/cli_policy.py`, policy fixtures, and related tests.
- T007 policy matcher operators: implemented in `src/ailuros/policy/matcher.py`, `src/ailuros/policy/operators.py`, `src/ailuros/utils/json_path.py`, and related tests.
- T008 before-tool-call governance flow: implemented in `src/ailuros/runtime/runtime.py`, `src/ailuros/policy/engine.py`, `src/ailuros/policy/decision_resolver.py`, decision models, and related tests.
- T009 governed tool wrapper: implemented in `src/ailuros/runtime/tool_wrapper.py`, runtime integration, and `tests/test_tool_wrapper.py`.
- T010 refund governance demo verification: covered by `tests/test_refund_demo.py` and the refund demo validation command recorded in `sdd/everrun-tasks.md`.

## Validation Contract

The metadata-only synchronization must preserve runtime behavior. The required validation commands are:

- `python -m pytest`
- `python -m ruff check .`
- `python examples/refund_agent/main.py`
- `python -m ailuros run list`

If any command fails, the task status should not be treated as final until the failure is reviewed without weakening runtime behavior or broadening the metadata-only scope.
