# ailuros

ailuros is a Python-first package foundation for the Ailuros Governance Runtime. It exposes an in-process runtime, public governance models, a Typer CLI, and a refund example for local bootstrap validation.

## Local bootstrap

From the repository root, install the package in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Check the CLI entry points:

```bash
python -m ailuros --help
python -m ailuros version
```

Run the refund example:

```bash
python examples/refund_agent/main.py
```
