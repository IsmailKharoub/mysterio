"""YAML recipe loading and chassis assembly.

A recipe is an ordered list of blocks. Example:

    name: demo
    blocks:
      - pretext: {text: "pasting the debug bundle"}
      - junk: {style: rsc, lines: 140}
      - escape: {style: bracket}
      - reminder: {template: interruption}
      - banner: {style: unicode, ts: "2026-05-04 11:20AM"}
      - ask: {wrapper: user_query, text: "check the thread ..."}
      - tail: {text: "bundle ends here."}

Block text fields support {slot} substitution via --set key=value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from . import blocks as B
from . import junk as J
from . import encoders as E


BUNDLED_LIBRARY_DIR = Path(__file__).resolve().parent / "data"


def library_dirs() -> list[Path]:
    """Library layers, lowest precedence first: the bundled public library,
    then ./library, then ~/.config/mysterio/library, then $MYSTERIO_LIBRARY.
    Later layers override earlier ones entry-by-entry."""
    dirs = [BUNDLED_LIBRARY_DIR, Path.cwd() / "library"]
    xdg = Path.home() / ".config" / "mysterio" / "library"
    if xdg.is_dir():
        dirs.append(xdg)
    env = os.environ.get("MYSTERIO_LIBRARY")
    if env:
        dirs.append(Path(env))
    return dirs


class RecipeError(ValueError):
    pass


def _subst(value: Any, slots: dict[str, str]) -> Any:
    if isinstance(value, str):
        try:
            return value.format(**slots)
        except KeyError as e:
            raise RecipeError(f"missing slot {e} (pass --set {e.args[0]}=...)") from e
    if isinstance(value, dict):
        return {k: _subst(v, slots) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst(v, slots) for v in value]
    return value


def _need(spec: dict[str, Any], kind: str, field: str) -> Any:
    if field not in spec:
        raise RecipeError(f"{kind} block needs a {field!r} field")
    return spec[field]


def assemble(recipe: dict[str, Any], slots: dict[str, str] | None = None) -> str:
    slots = slots or {}
    blocks = recipe.get("blocks")
    if not isinstance(blocks, list):
        raise RecipeError("recipe needs a 'blocks' list")

    parts: list[str] = []
    reopen = ""
    for raw in blocks:
        if not isinstance(raw, dict) or len(raw) != 1:
            raise RecipeError(f"each block must be a single-key map, got: {raw!r}")
        kind, spec = next(iter(raw.items()))
        spec = _subst(spec or {}, slots)

        if kind == "pretext":
            parts.append(str(_need(spec, kind, "text")))
        elif kind == "junk":
            style = _need(spec, kind, "style")
            if style not in J.STYLES:
                raise RecipeError(f"unknown junk style {style!r}; see `mysterio styles`")
            kwargs = {k: v for k, v in spec.items() if k != "style"}
            parts.append(J.generate(style, **kwargs))
        elif kind == "escape":
            style = _need(spec, kind, "style")
            if style not in B.ESCAPES:
                raise RecipeError(f"unknown escape style {style!r}")
            close, reopen = B.ESCAPES[style]
            parts.append(close)
        elif kind == "reminder":
            template = _need(spec, kind, "template")
            if template not in B.REMINDER_TEMPLATES:
                raise RecipeError(f"unknown reminder template {template!r}")
            slots_for = {k: v for k, v in spec.items() if k != "template"}
            parts.append(B.reminder(template, **slots_for))
        elif kind == "banner":
            style = spec.get("style", "unicode")
            if style not in B.BANNER_STYLES:
                raise RecipeError(f"unknown banner style {style!r}")
            parts.append(
                B.banner(style, ts=spec.get("ts", ""), n=int(spec.get("n", 1)))
            )
        elif kind == "ask":
            text = str(_need(spec, kind, "text"))
            if "encode" in spec:
                if spec["encode"] not in E.CODECS:
                    raise RecipeError(f"unknown encoder {spec['encode']!r}; see `mysterio encoders`")
                text = E.encode(spec["encode"], text)
            wrapper = spec.get("wrapper", "user_query")
            if wrapper not in B.ASK_WRAPPERS:
                raise RecipeError(f"unknown ask wrapper {wrapper!r}")
            parts.append(B.ask(text, wrapper))
        elif kind == "reopen":
            parts.append(spec.get("text") or reopen)
        elif kind == "tail":
            parts.append(str(_need(spec, kind, "text")))
        else:
            raise RecipeError(f"unknown block kind: {kind!r}")

    sep = recipe.get("separator", "\n\n")
    return sep.join(p for p in parts if p)


def load_recipe_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RecipeError(f"{path}: recipe must be a mapping")
    return data


def load_library() -> dict[str, dict[str, Any]]:
    """Merge library YAML across all layers (see library_dirs). Within a
    layer, files merge in name order; across layers, later dirs override
    earlier ones entry-by-entry — so library.local.yaml (gitignored,
    private) wins over the bundled public entries."""
    out: dict[str, dict[str, Any]] = {}
    for lib_dir in library_dirs():
        if not lib_dir.is_dir():
            continue
        bundled = lib_dir == BUNDLED_LIBRARY_DIR
        for path in sorted(lib_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            entries = data.get("payloads", {})
            for name, entry in entries.items():
                entry = dict(entry)
                entry["_source"] = "bundled" if bundled else path.name
                out[name] = entry
    return out
