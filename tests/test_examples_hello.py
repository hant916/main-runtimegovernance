from __future__ import annotations

import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

from hello import main


def test_hello_demo_output(capsys):
    main()
    captured = capsys.readouterr()
    out = captured.out
    assert "=== Decision ===" in out
    assert "=== Ordered Events ===" in out
    assert "=== Run Summary ===" in out
    assert "=== Replay Timeline ===" in out
    assert "=== Audit Summary ===" in out
    assert "Hello governance demo complete." in out
