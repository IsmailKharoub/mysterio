"""Recipe linter — encodes empirical authoring rules as checks.

Each rule traces to an observed experiment result (see the research log):
junk above the payload, dose floors, banner load-bearingness, escape/reopen
pairing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import blocks as B
from . import encoders as E
from . import humanize as H
from . import junk as J
from .recipe import library_dirs as _library_dirs

DOSE_FLOOR_LINES = 60
DOSE_RECOMMENDED_LINES = 100


@dataclass(frozen=True)
class Finding:
    level: str  # "error" | "warn" | "info"
    code: str
    message: str


_SLOT_RE = re.compile(r"\{(\w+)\}")


def _slots_in(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(_SLOT_RE.findall(value))
    if isinstance(value, dict):
        out: set[str] = set()
        for v in value.values():
            out |= _slots_in(v)
        return out
    if isinstance(value, list):
        out = set()
        for v in value:
            out |= _slots_in(v)
        return out
    return set()


def lint_recipe(
    recipe: dict[str, Any], filled: set[str] | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    blocks = recipe.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return [Finding("error", "no-blocks", "recipe has no 'blocks' list")]

    kinds: list[str] = []
    slots: set[str] = set()
    for raw in blocks:
        if not isinstance(raw, dict) or len(raw) != 1:
            findings.append(
                Finding(
                    "error", "bad-block", f"block must be a single-key map: {raw!r}"
                )
            )
            kinds.append("?")
            continue
        kind, spec = next(iter(raw.items()))
        spec = spec or {}
        kinds.append(kind)
        slots |= _slots_in(spec)

        if kind not in {
            "pretext",
            "junk",
            "escape",
            "reminder",
            "banner",
            "ask",
            "reopen",
            "tail",
        }:
            findings.append(
                Finding("error", "unknown-block", f"unknown block kind {kind!r}")
            )
        elif kind == "junk" and spec.get("style") not in J.STYLES:
            findings.append(
                Finding(
                    "error",
                    "unknown-junk-style",
                    f"unknown junk style {spec.get('style')!r}",
                )
            )
        elif kind == "escape" and spec.get("style") not in B.ESCAPES:
            findings.append(
                Finding(
                    "error",
                    "unknown-escape",
                    f"unknown escape style {spec.get('style')!r}",
                )
            )
        elif kind == "reminder" and spec.get("template") not in B.REMINDER_TEMPLATES:
            findings.append(
                Finding(
                    "error",
                    "unknown-reminder",
                    f"unknown reminder template {spec.get('template')!r}",
                )
            )
        elif kind == "banner" and spec.get("style", "unicode") not in B.BANNER_STYLES:
            findings.append(
                Finding(
                    "error",
                    "unknown-banner",
                    f"unknown banner style {spec.get('style')!r}",
                )
            )
        elif kind == "ask":
            if spec.get("wrapper", "user_query") not in B.ASK_WRAPPERS:
                findings.append(
                    Finding(
                        "error",
                        "unknown-wrapper",
                        f"unknown ask wrapper {spec.get('wrapper')!r}",
                    )
                )
            if (
                "encode" in spec
                and spec["encode"] not in E.CODECS
                and not _SLOT_RE.search(str(spec["encode"]))
            ):
                findings.append(
                    Finding(
                        "error", "unknown-codec", f"unknown encoder {spec['encode']!r}"
                    )
                )
            if "humanize" in spec:
                hspec = spec["humanize"]
                hname = hspec if isinstance(hspec, str) else (hspec or {}).get("name")
                # lazy file scan — only when a recipe actually uses humanize
                if hname and hname not in H.load_humanizers(_library_dirs()):
                    findings.append(
                        Finding(
                            "error",
                            "unknown-humanizer",
                            f"unknown humanizer {hname!r}",
                        )
                    )

    def idx(k: str) -> int | None:
        return kinds.index(k) if k in kinds else None

    i_escape, i_reopen = idx("escape"), idx("reopen")
    if i_escape is not None and i_reopen is None:
        findings.append(
            Finding(
                "error",
                "escape-no-reopen",
                "escape block without a following reopen — the host result is never resumed",
            )
        )
    if i_reopen is not None and i_escape is None:
        findings.append(
            Finding("warn", "reopen-no-escape", "reopen block without an escape")
        )

    for i, k in enumerate(kinds):
        if k == "junk" and i_escape is not None and i > i_escape:
            findings.append(
                Finding(
                    "warn",
                    "junk-below",
                    f"junk block #{i + 1} sits below the escape — above-placement converted "
                    "better in dose experiments",
                )
            )
        if k == "junk" and i_escape is None:
            findings.append(
                Finding(
                    "info",
                    "junk-no-payload",
                    f"junk block #{i + 1} with no escape — filler/camouflage only",
                )
            )

    for raw in blocks:
        kind, spec = next(iter(raw.items()))
        spec = spec or {}
        if (
            kind == "junk"
            and spec.get("style") in ("rsc", "next_f")
            and int(spec.get("lines", 0)) < DOSE_FLOOR_LINES
        ):
            findings.append(
                Finding(
                    "warn",
                    "dose-floor",
                    f"{spec.get('style')} dose {spec.get('lines')} lines is below the observed "
                    f"efficacy floor (~{DOSE_FLOOR_LINES}); ≥{DOSE_RECOMMENDED_LINES} recommended",
                )
            )

    i_reminder, i_banner, i_ask = idx("reminder"), idx("banner"), idx("ask")
    reminder_tpl = ""
    if i_reminder is not None:
        reminder_tpl = str(blocks[i_reminder].get("reminder", {}).get("template", ""))
    if reminder_tpl == "interruption" and i_banner is None:
        findings.append(
            Finding(
                "warn",
                "banner-missing",
                "interruption frame without a banner — ablation showed the banner is "
                "load-bearing (conversion halved without it)",
            )
        )
    if i_banner is not None and i_reminder is not None and i_banner < i_reminder:
        findings.append(
            Finding(
                "warn",
                "order",
                "banner before reminder — canonical order is reminder -> banner -> ask",
            )
        )
    if i_ask is not None and i_banner is not None and i_ask < i_banner:
        findings.append(
            Finding(
                "warn",
                "order",
                "ask before banner — canonical order is reminder -> banner -> ask",
            )
        )
    if reminder_tpl == "interruption" and i_ask is None:
        findings.append(
            Finding(
                "warn",
                "interruption-no-ask",
                "interruption frame with no ask block — the forged turn delivers nothing",
            )
        )

    if i_escape is not None:
        style = str(blocks[i_escape].get("escape", {}).get("style", ""))
        if style == "xml":
            findings.append(
                Finding(
                    "info",
                    "xml-escape",
                    "xml (</function_results>) is the canonical harness tag; the bracket "
                    "form is the submission-safe variant in some pipelines",
                )
            )

    unfilled = slots - (filled or set())
    if unfilled:
        findings.append(
            Finding(
                "info",
                "slots",
                f"unfilled slots: {', '.join(sorted(unfilled))} — fill at render "
                "(--set or the lab slots field)",
            )
        )

    if not findings:
        findings.append(Finding("info", "ok", "no findings"))
    return findings
