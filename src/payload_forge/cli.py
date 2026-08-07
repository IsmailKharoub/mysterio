"""pf — payload-forge command line."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import encoders as E
from . import junk as J
from . import recipe as R

app = typer.Typer(
    name="pf",
    help="Composable payload builder for prompt-injection red-team research.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def _parse_sets(sets: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in sets:
        if "=" not in item:
            raise typer.BadParameter(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


@app.command()
def junk(
    style: str = typer.Argument(..., help="Junk style (see `pf styles`)"),
    lines: int = typer.Option(140, "--lines", "-n", help="Line count (or rows)"),
    seed: str = typer.Option("rsc-chunk", "--seed", "-s", help="Deterministic seed"),
) -> None:
    """Print context-noise to stdout."""
    if style not in J.STYLES:
        err_console.print(f"unknown style {style!r}; see `pf styles`")
        raise typer.Exit(2)
    gen = J.STYLES[style].generate
    if style == "base64":
        print(gen(size=lines * 32, seed=seed))
    else:
        print(gen(lines=lines, seed=seed))


@app.command()
def styles() -> None:
    """List junk styles."""
    table = Table(title="junk styles")
    table.add_column("name", style="cyan")
    table.add_column("description")
    for name, s in J.STYLES.items():
        table.add_row(name, s.description)
    console.print(table)


@app.command()
def encode(
    text: str = typer.Argument(..., help="Text to transform ('-' for stdin)"),
    method: str = typer.Option(
        ..., "--method", "-m", help="Codec name (see `pf encoders`)"
    ),
    decode: bool = typer.Option(False, "--decode", "-d", help="Reverse the transform"),
) -> None:
    """Transform text with an encoder/decoder."""
    if text == "-":
        text = sys.stdin.read()
    if method not in E.CODECS:
        err_console.print(f"unknown method {method!r}; see `pf encoders`")
        raise typer.Exit(2)
    if decode:
        try:
            print(E.decode(method, text))
        except ValueError as e:
            err_console.print(str(e))
            raise typer.Exit(2) from e
    else:
        print(E.encode(method, text))


@app.command()
def encoders() -> None:
    """List text encoders."""
    table = Table(title="encoders")
    table.add_column("name", style="cyan")
    table.add_column("category", style="magenta")
    table.add_column("decodable")
    table.add_column("description")
    for c in E.CODECS.values():
        table.add_row(c.name, c.category, "yes" if c.decode else "-", c.description)
    console.print(table)


@app.command()
def build(
    recipe_path: Path = typer.Argument(..., help="Path to a recipe YAML"),
    sets: list[str] = typer.Option([], "--set", help="Slot substitution key=value"),
) -> None:
    """Assemble a chassis from a recipe file."""
    recipe = R.load_recipe_file(recipe_path)
    print(R.assemble(recipe, _parse_sets(sets)))


@app.command("use")
def use(
    name: str = typer.Argument(..., help="Library payload name (see `pf library`)"),
    sets: list[str] = typer.Option([], "--set", help="Slot substitution key=value"),
) -> None:
    """Render a payload from the library."""
    library = R.load_library()
    if name not in library:
        err_console.print(f"no library payload {name!r}; see `pf library`")
        raise typer.Exit(2)
    print(R.assemble(library[name], _parse_sets(sets)))


@app.command()
def library() -> None:
    """List library payloads (local/private entries included)."""
    library = R.load_library()
    if not library:
        err_console.print("library is empty — add YAML under library/")
        raise typer.Exit(1)
    table = Table(title="payload library")
    table.add_column("name", style="cyan")
    table.add_column("source")
    table.add_column("description")
    for name, entry in library.items():
        src = entry.get("_source", "?")
        private = src.endswith(".local.yaml")
        table.add_row(
            name,
            f"[red]{src}[/red]" if private else src,
            str(entry.get("description", "")),
        )
    console.print(table)


@app.command()
def stats(
    path: Optional[Path] = typer.Argument(
        None, help="File to measure (omit/'-' for stdin)"
    ),
) -> None:
    """Measure payload size: chars, lines, rough token estimate."""
    text = (
        sys.stdin.read()
        if (path is None or str(path) == "-")
        else path.read_text(encoding="utf-8")
    )
    table = Table(title="payload stats")
    table.add_column("metric", style="cyan")
    table.add_column("value", justify="right")
    table.add_row("chars", f"{len(text):,}")
    table.add_row("lines", f"{text.count(chr(10)) + 1:,}")
    table.add_row("words", f"{len(text.split()):,}")
    table.add_row("~tokens (chars/4)", f"{len(text) // 4:,}")
    console.print(table)
