"""mysterio command line."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import encoders as E
from . import junk as J
from . import lint as L
from . import recipe as R
from . import vary as V

app = typer.Typer(
    name="mysterio",
    help="Composable payload builder for prompt-injection red-team research.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def _emit(text: str, out: Optional[Path]) -> None:
    if out is None:
        print(text)
    else:
        out.write_text(text + "\n", encoding="utf-8")
        err_console.print(f"wrote {out} ({len(text):,} chars)")


def _parse_sets(sets: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in sets:
        if "=" not in item:
            raise typer.BadParameter(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def _format_payload(text: str, fmt: str) -> str:
    """Render for embedding. 'python' is a repr() literal safe to splice into
    .py sources; 'json' is a JSON string literal."""
    import json as _json

    if fmt == "raw":
        return text
    if fmt == "python":
        return repr(text)
    if fmt == "json":
        return _json.dumps(text)
    raise typer.BadParameter(f"--format expects raw|python|json, got {fmt!r}")


@app.command()
def junk(
    style: str = typer.Argument(..., help="Junk style (see `mysterio styles`)"),
    lines: int = typer.Option(140, "--lines", "-n", help="Line count (or rows)"),
    approx_tokens: Optional[int] = typer.Option(
        None,
        "--approx-tokens",
        "-t",
        help="Token budget — resolved to lines by self-calibration (overrides --lines)",
    ),
    seed: str = typer.Option("rsc-chunk", "--seed", "-s", help="Deterministic seed"),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to file instead of stdout"
    ),
) -> None:
    """Print context-noise to stdout."""
    if style not in J.STYLES:
        err_console.print(f"unknown style {style!r}; see `mysterio styles`")
        raise typer.Exit(2)
    if approx_tokens is not None:
        lines = J.lines_for_tokens(style, approx_tokens, seed)
        err_console.print(f"~{approx_tokens} tokens -> {lines} lines")
    gen = J.STYLES[style].generate
    if style == "base64":
        _emit(gen(size=lines * 32, seed=seed), out)
    else:
        _emit(gen(lines=lines, seed=seed), out)


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
        ..., "--method", "-m", help="Codec name (see `mysterio encoders`)"
    ),
    decode: bool = typer.Option(False, "--decode", "-d", help="Reverse the transform"),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to file instead of stdout"
    ),
) -> None:
    """Transform text with an encoder/decoder. Use -m all to preview every codec."""
    if text == "-":
        text = sys.stdin.read()
    if method == "all":
        table = Table(title=f"all encoders on {text[:40]!r}")
        table.add_column("codec", style="cyan")
        table.add_column("category", style="magenta")
        table.add_column("output")
        for c in E.CODECS.values():
            rendered = c.encode(text)
            shown = repr(rendered) if c.category == "invisible" else rendered
            if len(shown) > 72:
                shown = shown[:69] + "..."
            table.add_row(c.name, c.category, shown)
        console.print(table)
        return
    if method not in E.CODECS:
        err_console.print(f"unknown method {method!r}; see `mysterio encoders`")
        raise typer.Exit(2)
    if decode:
        try:
            _emit(E.decode(method, text), out)
        except ValueError as e:
            err_console.print(str(e))
            raise typer.Exit(2) from e
    else:
        _emit(E.encode(method, text), out)


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
    fmt: str = typer.Option(
        "raw", "--format", "-f", help="Output format: raw | python | json"
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to file instead of stdout"
    ),
) -> None:
    """Assemble a chassis from a recipe file."""
    recipe = R.load_recipe_file(recipe_path)
    _emit(_format_payload(R.assemble(recipe, _parse_sets(sets)), fmt), out)


@app.command("use")
def use(
    name: str = typer.Argument(
        ..., help="Library payload name (see `mysterio library`)"
    ),
    sets: list[str] = typer.Option([], "--set", help="Slot substitution key=value"),
    fmt: str = typer.Option(
        "raw", "--format", "-f", help="Output format: raw | python | json"
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to file instead of stdout"
    ),
) -> None:
    """Render a payload from the library."""
    library = R.load_library()
    if name not in library:
        err_console.print(f"no library payload {name!r}; see `mysterio library`")
        raise typer.Exit(2)
    _emit(_format_payload(R.assemble(library[name], _parse_sets(sets)), fmt), out)


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
def check(
    target: str = typer.Argument(..., help="Recipe YAML path, or library payload name"),
) -> None:
    """Lint a recipe against the empirical authoring rules."""
    path = Path(target)
    if path.is_file():
        recipe = R.load_recipe_file(path)
        source = str(path)
    else:
        library = R.load_library()
        if target not in library:
            err_console.print(f"{target!r} is neither a file nor a library payload")
            raise typer.Exit(2)
        recipe = library[target]
        source = f"library:{target}"

    findings = L.lint_recipe(recipe)
    table = Table(title=f"check: {source}")
    table.add_column("level")
    table.add_column("code", style="cyan")
    table.add_column("message")
    level_style = {"error": "red", "warn": "yellow", "info": "dim"}
    for f in findings:
        table.add_row(
            f"[{level_style[f.level]}]{f.level}[/{level_style[f.level]}]",
            f.code,
            f.message,
        )
    console.print(table)
    if any(f.level == "error" for f in findings):
        raise typer.Exit(1)


@app.command()
def vary(
    target: str = typer.Argument(..., help="Recipe YAML path, or library payload name"),
    varies: list[str] = typer.Option(
        [], "--vary", "-v", help="Sweep spec kind.field=v1,v2,... (repeatable)"
    ),
    zip_mode: bool = typer.Option(
        False, "--zip", help="Pair values positionally instead of cross product"
    ),
    sets: list[str] = typer.Option([], "--set", help="Slot substitution key=value"),
    out_dir: Optional[Path] = typer.Option(
        None, "--out-dir", help="Write arms here (omit for dry run)"
    ),
    recipes: bool = typer.Option(
        False, "--recipes", help="Write arm recipe YAMLs instead of rendered payloads"
    ),
) -> None:
    """Sweep one or more recipe fields and emit one arm per combination."""
    import yaml as _yaml

    path = Path(target)
    if path.is_file():
        recipe = R.load_recipe_file(path)
    else:
        library = R.load_library()
        if target not in library:
            err_console.print(f"{target!r} is neither a file nor a library payload")
            raise typer.Exit(2)
        recipe = library[target]

    try:
        arms = V.vary_recipe(recipe, varies, zip_mode)
    except ValueError as e:
        err_console.print(str(e))
        raise typer.Exit(2) from e

    slots = _parse_sets(sets)
    if out_dir is None:
        table = Table(
            title=f"vary: {len(arms)} arm(s) (dry run — pass --out-dir to write)"
        )
        table.add_column("arm", style="cyan")
        for label, _ in arms:
            table.add_row(label)
        console.print(table)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    for label, arm in arms:
        dest = out_dir / (f"{label}.yaml" if recipes else f"{label}.txt")
        if recipes:
            dest.write_text(_yaml.safe_dump(arm, sort_keys=False), encoding="utf-8")
        else:
            dest.write_text(R.assemble(arm, slots) + "\n", encoding="utf-8")
        err_console.print(f"wrote {dest}")


def _resolve_recipe(target: str) -> tuple[dict, str]:
    path = Path(target)
    if path.is_file():
        return R.load_recipe_file(path), str(path)
    library = R.load_library()
    if target not in library:
        raise typer.BadParameter(f"{target!r} is neither a file nor a library payload")
    return library[target], f"library:{target}"


@app.command()
def diff(
    left: str = typer.Argument(..., help="Left recipe (file or library name)"),
    right: str = typer.Argument(..., help="Right recipe (file or library name)"),
) -> None:
    """Block-level diff between two recipes."""
    import yaml as _yaml

    la, lsrc = _resolve_recipe(left)
    ra, rsrc = _resolve_recipe(right)
    lb = la.get("blocks", [])
    rb = ra.get("blocks", [])

    table = Table(title=f"diff: {lsrc} vs {rsrc}")
    table.add_column("block", justify="right")
    table.add_column("left", style="cyan")
    table.add_column("right", style="green")
    changed = 0
    for i in range(max(len(lb), len(rb))):
        l = _yaml.safe_dump(lb[i], sort_keys=False).strip() if i < len(lb) else "—"
        r = _yaml.safe_dump(rb[i], sort_keys=False).strip() if i < len(rb) else "—"
        if l != r:
            changed += 1
            table.add_row(str(i + 1), l, r)
    if changed:
        console.print(table)
        console.print(f"{changed} block(s) differ")
    else:
        console.print("recipes are block-identical")


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
