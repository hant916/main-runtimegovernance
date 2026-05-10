import uuid


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def new_run_id() -> str:
    return _new_id("run")


def new_step_id() -> str:
    return _new_id("step")


def new_event_id() -> str:
    return _new_id("evt")


def new_decision_id() -> str:
    return _new_id("dec")


def new_evaluation_id() -> str:
    return _new_id("eval")


def new_audit_id() -> str:
    return _new_id("audit")
