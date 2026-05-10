{
  "version": "v0.1.0",
  "batch": "python-first-runtime-core",
  "tasks": [
    {
      "id": "T001",
      "title": "Bootstrap Python package with runtime CLI and refund example",
      "goal": "Create the Python-first Ailuros package foundation using Python 3.11+, Pydantic v2, Typer, pytest, and ruff. This replaces the earlier TypeScript-first runtime direction with an in-process Python SDK foundation.",
      "depends_on": [],
      "files": [
        "pyproject.toml",
        "README.md",
        ".gitignore",
        "src/ailuros/__init__.py",
        "src/ailuros/__main__.py",
        "src/ailuros/runtime.py",
        "src/ailuros/cli.py",
        "tests/test_smoke.py",
        "examples/refund_agent/main.py"
      ],
      "steps": [
        "Create a Python package named ailuros under src/ailuros.",
        "Configure pyproject.toml for Python 3.11+, Pydantic v2, Typer, pytest, ruff, and one type checker such as mypy or pyright.",
        "Expose a console script named ailuros mapped to ailuros.cli:app.",
        "Implement placeholder AilurosRuntime with name='AilurosRuntime' and get_version() returning '0.0.0'.",
        "Export AilurosRuntime from src/ailuros/__init__.py.",
        "Implement Typer CLI with --help and version command.",
        "Implement python -m ailuros entrypoint.",
        "Create a minimal refund example that imports and instantiates AilurosRuntime.",
        "Add smoke tests for import, version, and runtime instantiation.",
        "Do not implement database, policy, replay, path validation, HTTP server, or framework adapters in this task."
      ],
      "acceptance": [
        "python -m ailuros --help prints a usable CLI help message containing Ailuros Governance Runtime.",
        "python -m ailuros version prints 0.0.0.",
        "AilurosRuntime can be imported from ailuros.",
        "examples/refund_agent/main.py runs without policy or database logic.",
        "pytest passes.",
        "ruff check passes."
      ],
      "validate": [
        "python -m pip install -e \".[dev]\"",
        "python -m pytest",
        "python -m ruff check .",
        "python -m ailuros --help",
        "python -m ailuros version",
        "python examples/refund_agent/main.py"
      ],
      "status": "todo"
    },
    {
      "id": "T002",
      "title": "Define Python runtime data models",
      "goal": "Add Pydantic v2 models and explicit enums for the canonical Ailuros runtime event contract, including runs, steps, events, decisions, policies, evaluations, replay, audit, and regression results.",
      "depends_on": [
        "T001"
      ],
      "files": [
        "src/ailuros/models/common.py",
        "src/ailuros/models/run.py",
        "src/ailuros/models/step.py",
        "src/ailuros/models/event.py",
        "src/ailuros/models/decision.py",
        "src/ailuros/models/policy.py",
        "src/ailuros/models/evaluation.py",
        "src/ailuros/models/replay.py",
        "src/ailuros/models/audit.py",
        "src/ailuros/models/regression.py",
        "src/ailuros/models/__init__.py",
        "src/ailuros/__init__.py",
        "tests/test_models.py"
      ],
      "steps": [
        "Create common Environment and Severity StrEnum values.",
        "Create RunStatus and Run model with timezone-aware datetime fields.",
        "Create StepType, StepStatus, and Step models.",
        "Create RuntimeEventType enum containing canonical events: run_started, user_input_received, input_classified, agent_plan_created, agent_message, llm_request, llm_response, tool_call_requested, path_validation_result, policy_evaluation_result, governance_decision, tool_call_executed, tool_call_blocked, tool_result_received, output_generated, evaluation_result, human_review_requested, human_review_completed, run_completed, run_failed, replay_started, replay_completed, regression_comparison_result, payload_redacted.",
        "Create RuntimeEvent model with event_id, run_id, optional step_id, event_type, timestamp, and payload.",
        "Create GovernanceDecisionType and GovernanceDecision model.",
        "Create PolicyOperator and Policy model using snake_case canonical fields such as tool_name and arguments.amount_eur.",
        "Create EvaluationFinding and EvaluationResult models.",
        "Create ReplayResult, AuditReport, and RegressionComparisonResult models.",
        "Export all public models from src/ailuros/models/__init__.py and re-export key models from src/ailuros/__init__.py."
      ],
      "acceptance": [
        "All models serialize to JSON with Pydantic v2.",
        "Invalid enum values are rejected.",
        "RuntimeEventType contains every canonical event required by the integration contract.",
        "Policy model accepts valid JSON policy definitions.",
        "No storage, policy matching, runtime behavior, CLI workflow, or server logic is added."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T003",
      "title": "Implement SQLite append-only runtime storage",
      "goal": "Create a local SQLite storage layer for Ailuros runtime records using the Python standard sqlite3 module and append-only event storage.",
      "depends_on": [
        "T002"
      ],
      "files": [
        "src/ailuros/storage/sqlite_storage.py",
        "src/ailuros/storage/migrations/001_initial.sql",
        "src/ailuros/storage/__init__.py",
        "src/ailuros/errors.py",
        "tests/test_sqlite_storage.py"
      ],
      "steps": [
        "Create SQLite tables for runs, steps, events, governance_decisions, evaluations, audit_reports, replay_runs, and migrations.",
        "Add idx_events_run_sequence index on events(run_id, sequence).",
        "Implement SQLiteStorage with init(), create_run(), get_run(), list_runs(), update_run_status(), create_step(), get_step(), update_step_status(), append_event(), list_events(), save_governance_decision(), save_evaluation(), save_audit_report(), and save_replay_result().",
        "Store metadata, payloads, findings, key events, controls, differences, and matched policy IDs as JSON text.",
        "Use Pydantic model_dump(mode='json') or equivalent safe conversion before persistence.",
        "Convert JSON text back to model objects on reads.",
        "Assign monotonically increasing per-run event sequence inside append_event().",
        "Do not expose public methods to update or delete events.",
        "Create explicit errors: AilurosStorageError, AilurosNotFoundError, and AilurosDataCorruptionError.",
        "Use temporary SQLite files in tests."
      ],
      "acceptance": [
        "Storage initializes a missing database.",
        "Migrations run once.",
        "Runs, steps, events, decisions, evaluations, audit reports, and replay results persist successfully.",
        "Events list in sequence order.",
        "JSON payloads round-trip correctly.",
        "Corrupt JSON raises an explicit data corruption error.",
        "There is no public event update or delete API."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T004",
      "title": "Implement AilurosRuntime lifecycle APIs",
      "goal": "Make the Python SDK usable enough for a host agent runtime to start a governed run, record events, record tool results, complete runs, fail runs, and inspect events.",
      "depends_on": [
        "T003"
      ],
      "files": [
        "src/ailuros/runtime/runtime.py",
        "src/ailuros/runtime/ids.py",
        "src/ailuros/runtime/clock.py",
        "src/ailuros/runtime/__init__.py",
        "src/ailuros/runtime.py",
        "src/ailuros/__init__.py",
        "tests/test_runtime_lifecycle.py"
      ],
      "steps": [
        "Implement AilurosRuntime constructor accepting agent_id, environment, storage_path, and optional metadata.",
        "Create now_utc() returning timezone-aware UTC datetime.",
        "Create ID helpers using uuid.uuid4().hex with prefixes run_, step_, evt_, dec_, eval_, and audit_.",
        "Implement start_run(input, user_id=None, metadata=None) to create a Run, persist it, and append run_started and user_input_received events.",
        "Implement complete_run(run_id, output=None, status=RunStatus.COMPLETED, metadata=None) to verify run existence, append output_generated when output is present, update run status, and append run_completed.",
        "Implement fail_run(run_id, message, code=None, metadata=None) to update status to failed and append run_failed.",
        "Implement record_event(run_id, event_type, payload=None, step_id=None) to verify run existence and append a RuntimeEvent.",
        "Implement record_tool_result(run_id, tool_name, result, arguments=None, step_id=None) to append tool_result_received with snake_case payload keys.",
        "Implement list_events(run_id) to return storage events in sequence order.",
        "Keep src/ailuros/runtime.py as compatibility re-export if runtime becomes a package."
      ],
      "acceptance": [
        "start_run creates a run and appends run_started and user_input_received.",
        "complete_run updates run status and appends run_completed.",
        "fail_run updates status to failed and appends run_failed.",
        "record_event appends custom events.",
        "record_tool_result appends tool_result_received.",
        "Unknown run IDs fail clearly.",
        "No policy, path, evaluation, replay, or HTTP server logic is added."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T005",
      "title": "Implement CLI run list and show timeline",
      "goal": "Add Typer CLI commands for inspecting Ailuros runs and event timelines from the terminal without a UI.",
      "depends_on": [
        "T004"
      ],
      "files": [
        "src/ailuros/cli.py",
        "src/ailuros/cli_run.py",
        "src/ailuros/storage/sqlite_storage.py",
        "tests/test_cli_run.py"
      ],
      "steps": [
        "Add Typer subcommands under ailuros run.",
        "Implement ailuros run list to print recent runs from SQLite.",
        "Implement ailuros run show <run_id> to print run metadata and ordered event timeline.",
        "Support database path resolution using --db first, AILUROS_DB second, and ./ailuros.sqlite as default.",
        "Render timeline event sequence numbers in ascending order.",
        "Render tool_call_requested, governance_decision, tool_call_blocked, and evaluation_result payload highlights when present.",
        "Return non-zero CLI exit for missing run ID, unknown run ID, and missing database.",
        "Add Typer CliRunner tests for empty database, one run, known run show, unknown run show, env DB path, and CLI --db path."
      ],
      "acceptance": [
        "ailuros run list works with default DB path.",
        "ailuros run show <run_id> prints ordered events.",
        "AILUROS_DB and --db both work.",
        "Errors are clear and non-zero.",
        "No dashboard, TUI, policy logic, replay logic, or server logic is added."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m ailuros run list"
      ],
      "status": "todo"
    },
    {
      "id": "T006",
      "title": "Implement JSON policy loader and validation CLI",
      "goal": "Allow developers to define governance policies in JSON and validate them before runtime execution.",
      "depends_on": [
        "T004"
      ],
      "files": [
        "src/ailuros/policy/loader.py",
        "src/ailuros/policy/validator.py",
        "src/ailuros/policy/errors.py",
        "src/ailuros/policy/__init__.py",
        "src/ailuros/cli.py",
        "src/ailuros/cli_policy.py",
        "tests/policy/fixtures/valid_refund_policy.json",
        "tests/policy/fixtures/invalid_missing_id.json",
        "tests/policy/fixtures/invalid_unknown_operator.json",
        "tests/test_policy_loader.py",
        "tests/test_cli_policy.py"
      ],
      "steps": [
        "Implement PolicyLoader with load_file(), load_files(), and load_directory().",
        "Implement PolicyValidator with validate() and validate_many().",
        "Use Pydantic model validation for policy structure.",
        "Add custom PolicyValidationError with clear messages.",
        "Reject policies missing policy_id, version, match, or severity.",
        "Reject unknown decision, severity, and operator values.",
        "Validate operators nested inside match, scope, and requires_previous_steps.",
        "Implement ailuros policy validate <path> for a single JSON file or a directory of JSON files.",
        "Print number of validated policy files on success.",
        "Exit non-zero with file path and error message on invalid policy."
      ],
      "acceptance": [
        "Valid refund policy loads successfully.",
        "Invalid missing ID policy fails clearly.",
        "Invalid unknown operator policy fails clearly.",
        "Disabled policies still validate.",
        "Directory validation loads multiple JSON files.",
        "CLI validation works for success and failure.",
        "No policy matching or before_tool_call behavior is added."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m ailuros policy validate tests/policy/fixtures/valid_refund_policy.json"
      ],
      "status": "todo"
    },
    {
      "id": "T007",
      "title": "Implement policy matcher operators",
      "goal": "Implement deterministic policy matching for tool-call contexts using field paths and explicit condition operators.",
      "depends_on": [
        "T006"
      ],
      "files": [
        "src/ailuros/policy/matcher.py",
        "src/ailuros/policy/operators.py",
        "src/ailuros/utils/json_path.py",
        "src/ailuros/policy/__init__.py",
        "tests/test_json_path.py",
        "tests/test_policy_operators.py",
        "tests/test_policy_matcher.py"
      ],
      "steps": [
        "Create ToolCallContext model with environment, tool_name, arguments, and metadata.",
        "Implement get_by_path() for dot-separated paths such as arguments.amount_eur.",
        "Use a missing-value sentinel so missing fields are distinguishable from explicit null.",
        "Implement operators eq, neq, gt, gte, lt, lte, in, not_in, exists, not_exists, contains, and regex.",
        "Ensure numeric comparisons fail safely if actual or expected values are not numbers.",
        "Ensure invalid regex patterns fail safely with a match failure reason.",
        "Implement PolicyMatcher.matches(policy, context).",
        "Implement PolicyMatcher.match_details(policy, context) returning failed conditions.",
        "Require all scope conditions and all match conditions to pass.",
        "Treat plain values in policy match objects as eq comparisons."
      ],
      "acceptance": [
        "Nested field path matching works for arguments.amount_eur.",
        "Environment scope matching works.",
        "Every operator has positive and negative test coverage.",
        "Missing fields do not crash.",
        "Invalid regex does not crash.",
        "Matcher does not mutate policy or context inputs."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T008",
      "title": "Implement before_tool_call governance decision flow",
      "goal": "Add the main runtime interception point that records a planned tool call, evaluates policies, stores governance decisions, and returns whether execution is allowed.",
      "depends_on": [
        "T007"
      ],
      "files": [
        "src/ailuros/runtime/runtime.py",
        "src/ailuros/policy/engine.py",
        "src/ailuros/policy/decision_resolver.py",
        "src/ailuros/models/decision.py",
        "src/ailuros/policy/__init__.py",
        "tests/test_decision_resolver.py",
        "tests/test_before_tool_call.py"
      ],
      "steps": [
        "Extend AilurosRuntime constructor to accept policies as a list of JSON file paths.",
        "Load policies during runtime initialization or lazily before first policy evaluation.",
        "Implement PolicyEngine.evaluate_tool_call(context) returning matched policies and counts.",
        "Implement DecisionResolver with decision priority block, require_review, sanitize, warn, allow.",
        "Use severity priority critical, high, medium, low as tie-breaker.",
        "Use deterministic lexical policy_id ordering as final tie-breaker.",
        "Implement before_tool_call(run_id, tool_name, arguments=None, metadata=None).",
        "Append tool_call_requested before policy evaluation.",
        "Append policy_evaluation_result with matched_policy_ids, evaluated_policy_count, and matched_policy_count.",
        "Append governance_decision with final decision.",
        "Append tool_call_blocked when decision.allowed is false.",
        "Return GovernanceDecision."
      ],
      "acceptance": [
        "No matching policy returns allow with allowed true.",
        "High-value refund policy returns require_review with allowed false.",
        "Block policy returns block.",
        "Warn policy returns allowed true.",
        "Disabled policies are ignored.",
        "Multiple matching policies resolve deterministically by decision priority, severity, and policy ID.",
        "Required events are persisted.",
        "Unknown run IDs fail clearly."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T009",
      "title": "Implement generic governed tool wrapper",
      "goal": "Add runtime.wrap_tool() so host agents can govern tool execution without manually calling before and after hooks around every tool.",
      "depends_on": [
        "T008"
      ],
      "files": [
        "src/ailuros/runtime/runtime.py",
        "src/ailuros/runtime/tool_wrapper.py",
        "src/ailuros/runtime/__init__.py",
        "tests/test_tool_wrapper.py"
      ],
      "steps": [
        "Create ToolExecutionResult model with blocked, decision, result, and error fields.",
        "Implement runtime.wrap_tool(name, fn) returning a callable.",
        "Require wrapped function calls to provide run_id as a keyword argument.",
        "Treat all other keyword arguments as tool arguments.",
        "Call before_tool_call before executing the original function.",
        "If decision.allowed is false, do not execute the original function and return ToolExecutionResult(blocked=True).",
        "If decision.allowed is true, execute the original function.",
        "Implement after_tool_call(run_id, tool_name, arguments=None, result=None, metadata=None).",
        "Have after_tool_call append tool_call_executed and tool_result_received events.",
        "Return ToolExecutionResult(blocked=False, decision=decision, result=result) for allowed calls."
      ],
      "acceptance": [
        "Allowed wrapped tool executes original function.",
        "Blocked wrapped tool never executes original function.",
        "after_tool_call records tool_call_executed and tool_result_received for successful calls.",
        "Missing run_id fails clearly.",
        "Tool arguments are passed correctly.",
        "Returned result always includes the governance decision."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python -m mypy src"
      ],
      "status": "todo"
    },
    {
      "id": "T010",
      "title": "Implement Python refund governance demo",
      "goal": "Create the first end-to-end deterministic demo proving that Ailuros can intercept a risky refund tool call and prevent execution before damage.",
      "depends_on": [
        "T009"
      ],
      "files": [
        "examples/refund_agent/main.py",
        "examples/refund_agent/policies/refund.json",
        "examples/refund_agent/README.md",
        "tests/test_refund_demo.py"
      ],
      "steps": [
        "Create examples/refund_agent/policies/refund.json with refund.high_value_requires_review policy for payment.issue_refund when arguments.amount_eur > 500.",
        "Implement get_order_status(order_id) returning delivered status and amount_eur 780.",
        "Implement issue_refund(order_id, amount_eur, reason) so the test can detect if it was called; it must not be called when governance disallows execution.",
        "Create AilurosRuntime with agent_id refund_demo_agent, environment development, storage_path ./ailuros.sqlite, and refund policy file.",
        "Start a run for input 'I want a refund for order ORD-9231.'.",
        "Record order.get_status result through record_tool_result.",
        "Wrap issue_refund with runtime.wrap_tool(name='payment.issue_refund', fn=issue_refund).",
        "Call wrapped refund tool with run_id, order_id, amount_eur 780, and reason customer_request.",
        "When blocked or requiring review, complete the run as requires_review and print decision and reason.",
        "Add README commands for running the demo and inspecting timeline with ailuros run list and ailuros run show."
      ],
      "acceptance": [
        "Demo runs locally without real LLM or payment API.",
        "Refund function is not executed when decision is require_review.",
        "Run completes as requires_review.",
        "Timeline contains tool_call_requested, policy_evaluation_result, governance_decision, tool_call_blocked, and run_completed.",
        "Tests verify no successful payment.issue_refund tool result exists."
      ],
      "validate": [
        "python -m pytest",
        "python -m ruff check .",
        "python examples/refund_agent/main.py",
        "python -m ailuros run list"
      ],
      "status": "todo"
    }
  ]
}