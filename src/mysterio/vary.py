"""Parameter sweeps: generate arm variants of a recipe by varying fields.

A vary spec addresses blocks by kind: ``junk.lines=60,100,140`` applies to
every junk block in the recipe. Multiple specs produce a cross product by
default (systematic sweep) or a zip with --zip (paired ablation).
"""

from __future__ import annotations

import copy
import inspect
import itertools
from typing import Any

from . import junk as J

# Validatable fields per block kind. Junk fields come from each generator's
# signature (they differ per style); unknown kinds stay lenient.
_BLOCK_FIELDS: dict[str, set[str]] = {
    "pretext": {"text"},
    "escape": {"style"},
    "reminder": {"template", "n_messages", "channel", "entry_id", "entry_type"},
    "banner": {"style", "ts", "n"},
    "ask": {"wrapper", "text", "encode"},
    "reopen": {"text"},
    "tail": {"text"},
}


def _valid_fields(recipe: dict[str, Any], kind: str) -> set[str]:
    if kind != "junk":
        return _BLOCK_FIELDS.get(kind, set())
    fields = {"style"}
    for raw in recipe.get("blocks", []):
        if isinstance(raw, dict) and list(raw) == ["junk"]:
            style = (raw["junk"] or {}).get("style")
            if style in J.STYLES:
                fields |= set(inspect.signature(J.STYLES[style].generate).parameters)
    return fields


def parse_value(raw: str) -> Any:
    if raw.lstrip("-").isdigit():
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        return raw


def parse_vary(spec: str) -> tuple[str, list[Any]]:
    """'junk.lines=60,100,140' -> ('junk.lines', [60, 100, 140])"""
    if "=" not in spec:
        raise ValueError(f"vary spec expects kind.field=v1,v2,... got {spec!r}")
    path, values = spec.split("=", 1)
    if "." not in path:
        raise ValueError(f"vary spec expects kind.field, got {path!r}")
    vals = [parse_value(v) for v in values.split(",")]
    if not vals:
        raise ValueError(f"vary spec {spec!r} has no values")
    return path, vals


def apply_vary(recipe: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """Set kind.field=value on every block of that kind (returns a copy).
    Validates the field name up front so a typo fails the whole sweep —
    dry run included — instead of crashing at render time."""
    kind, field = path.split(".", 1)
    blocks = [
        next(iter(r.items()))
        for r in recipe.get("blocks", [])
        if isinstance(r, dict) and len(r) == 1
    ]
    if kind not in {k for k, _ in blocks}:
        raise ValueError(f"no {kind!r} block to apply {path!r} to")
    valid = _valid_fields(recipe, kind)
    if valid and field not in valid:
        raise ValueError(
            f"unknown field {path!r} — valid {kind} fields: {', '.join(sorted(valid))}"
        )
    out = copy.deepcopy(recipe)
    for raw in out.get("blocks", []):
        if isinstance(raw, dict) and len(raw) == 1:
            k, spec = next(iter(raw.items()))
            if k == kind and isinstance(spec, dict):
                spec[field] = value
    return out


def vary_recipe(
    recipe: dict[str, Any],
    specs: list[str],
    zip_mode: bool = False,
) -> list[tuple[str, dict[str, Any]]]:
    """Return [(label, recipe)] for each arm. Labels look like
    'junk.lines-140__banner.style-ascii'."""
    parsed = [parse_vary(s) for s in specs]
    if not parsed:
        return [("base", recipe)]

    paths = [p for p, _ in parsed]
    value_lists = [v for _, v in parsed]

    combos: list[tuple[Any, ...]]
    if zip_mode:
        lengths = {len(v) for v in value_lists}
        if len(lengths) != 1:
            raise ValueError(
                "--zip requires all vary specs to have the same number of values"
            )
        combos = list(zip(*value_lists))
    else:
        combos = list(itertools.product(*value_lists))

    arms: list[tuple[str, dict[str, Any]]] = []
    for combo in combos:
        label = "__".join(f"{p}-{v}" for p, v in zip(paths, combo))
        arm = recipe
        for p, v in zip(paths, combo):
            arm = apply_vary(arm, p, v)
        arms.append((_slug(label), arm))
    return arms


def _slug(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in label)
