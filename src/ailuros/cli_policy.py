from pathlib import Path

import typer

from ailuros.policy import PolicyLoader, PolicyValidationError

app = typer.Typer(help="Validate JSON policies.")


@app.command("validate")
def validate_policy(path: Path) -> None:
    try:
        loader = PolicyLoader()
        if path.is_dir():
            policies = loader.load_directory(path, strict=True)
        else:
            policies = [loader.load_file(path)]
    except PolicyValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Validated {len(policies)} policy file(s).")
