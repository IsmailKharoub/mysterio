"""Humanification — deterministic, seeded transforms that make an ask read
like a person wrote it: keyboard typos, dictation voice, register shifts.

Bundled humanizers are public and generic. Private ones layer on top from
`humanizers.yaml` / `humanizers.local.yaml` files in the library search path
(./library, ~/.config/mysterio/library, $MYSTERIO_LIBRARY) — same override
semantics as the payload library, and `*.local.yaml` is gitignored.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class HumanizeError(Exception):
    pass


# QWERTY adjacency — the classic fumble source.
_NEIGHBORS = {
    "q": "wa", "w": "qeas", "e": "wrds", "r": "etdf", "t": "ryfg",
    "y": "tugh", "u": "yijh", "i": "uojk", "o": "ipkl", "p": "ol",
    "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc",
    "g": "ftyhvb", "h": "gyujnb", "j": "huiknm", "k": "jiolm",
    "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb",
    "b": "vghn", "n": "bhjm", "m": "njk",
}

_WORD = r"\b{}\b"


@dataclass
class Humanizer:
    name: str
    description: str = ""
    lowercase: bool = False
    drop_punctuation: bool = False
    starters: tuple[str, ...] = ()        # optional opener, "" allowed
    replacements: dict[str, str] = field(default_factory=dict)
    fillers: tuple[str, ...] = ()
    filler_rate: float = 0.0              # per word-gap probability
    typo_rate: float = 0.0                # per alpha-char probability
    ellipsis: bool = False                # trailing "..."
    prompt: str = ""                      # style instructions for LLM rewrite
    source: str = "bundled"

    def apply(self, text: str, seed: str | None = None) -> str:
        rng = random.Random(f"{self.name}:{seed or 'default'}")
        out = text.strip()
        if self.starters:
            opener = rng.choice(self.starters)
            if opener:
                out = f"{opener} {out}"
        if self.lowercase:
            out = out.lower()
        for src, dst in self.replacements.items():
            out = re.sub(_WORD.format(re.escape(src)), dst, out, flags=re.IGNORECASE)
        if self.typo_rate:
            out = _typoify(out, self.typo_rate, rng)
        if self.fillers and self.filler_rate:
            out = _inject_fillers(out, self.fillers, self.filler_rate, rng)
        if self.drop_punctuation:
            out = re.sub(r"[.,;:!?]+", " ", out)
            out = re.sub(r"\s+", " ", out).strip()
        if self.ellipsis:
            out = out.rstrip(".") + "..."
        return out


def _typoify(text: str, rate: float, rng: random.Random) -> str:
    chars = list(text)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch.isalpha() and rng.random() < rate:
            roll = rng.random()
            if roll < 0.6 and ch.lower() in _NEIGHBORS:
                sub = rng.choice(_NEIGHBORS[ch.lower()])
                chars[i] = sub.upper() if ch.isupper() else sub
            elif roll < 0.8 and i + 1 < len(chars) and chars[i + 1].isalpha():
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
                i += 1
            else:
                chars[i] = ""
        i += 1
    return "".join(chars)


def _inject_fillers(
    text: str, fillers: tuple[str, ...], rate: float, rng: random.Random
) -> str:
    words = text.split(" ")
    out = []
    for word in words:
        if out and rng.random() < rate:
            out.append(rng.choice(fillers))
        out.append(word)
    return " ".join(out)


BUNDLED: dict[str, Humanizer] = {
    h.name: h
    for h in [
        Humanizer(
            "typos",
            "keyboard fumbles — adjacent keys, transpositions, dropped letters",
            typo_rate=0.03,
            prompt=(
                "typed fast on a phone keyboard: a few realistic adjacent-key "
                "typos, maybe a transposed or dropped letter, otherwise normal "
                "capitalization and punctuation"
            ),
        ),
        Humanizer(
            "voice-note",
            "dictated on the go — lowercase, no punctuation, um/uh fillers",
            lowercase=True,
            drop_punctuation=True,
            starters=("hey so", "ok so", "sorry", ""),
            fillers=("uh", "um", "like"),
            filler_rate=0.08,
            prompt=(
                "dictated as a voice note while doing something else: all "
                "lowercase, no punctuation, speech fillers (um, uh, like) used "
                "sparingly, slight run-on feel, maybe a false start"
            ),
        ),
        Humanizer(
            "casual",
            "relaxed register — lowercase, soft opener, light abbreviations",
            lowercase=True,
            starters=("hey,", "hi,", ""),
            replacements={"please": "pls", "thanks": "thx"},
            prompt=(
                "casual chat register: lowercase, relaxed opener like 'hey,' "
                "where it fits, light abbreviations (pls, thx), friendly and "
                "unhurried"
            ),
        ),
        Humanizer(
            "rushed",
            "typed in a hurry — text-speak, dropped punctuation, some typos",
            lowercase=True,
            drop_punctuation=True,
            typo_rate=0.02,
            replacements={
                "you": "u", "your": "ur", "are": "r",
                "please": "pls", "because": "cuz",
            },
            prompt=(
                "typed in a hurry: text-speak abbreviations (u, ur, pls, cuz), "
                "dropped punctuation, lowercase, terse, a typo or two"
            ),
        ),
        Humanizer(
            "formal",
            "register shift up — contractions expanded, no slang",
            replacements={
                "don't": "do not", "can't": "cannot", "won't": "will not",
                "i'm": "I am", "it's": "it is", "that's": "that is",
            },
            prompt=(
                "polished and formal: complete sentences, contractions "
                "expanded, no slang, measured and courteous"
            ),
        ),
    ]
}


def _from_spec(name: str, spec: dict[str, Any], source: str) -> Humanizer:
    known = {
        "description", "lowercase", "drop_punctuation", "starters",
        "replacements", "fillers", "filler_rate", "typo_rate", "ellipsis",
        "prompt",
    }
    unknown = set(spec) - known
    if unknown:
        raise HumanizeError(
            f"{source}: humanizer {name!r} has unknown fields: "
            f"{', '.join(sorted(unknown))} (known: {', '.join(sorted(known))})"
        )
    try:
        filler_rate = float(spec.get("filler_rate", 0.0))
        typo_rate = float(spec.get("typo_rate", 0.0))
    except (TypeError, ValueError) as e:
        raise HumanizeError(
            f"{source}: humanizer {name!r} rates must be numbers — {e}"
        ) from e
    return Humanizer(
        name,
        description=str(spec.get("description", "")),
        lowercase=bool(spec.get("lowercase", False)),
        drop_punctuation=bool(spec.get("drop_punctuation", False)),
        starters=tuple(spec.get("starters", ())),
        replacements=dict(spec.get("replacements", {})),
        fillers=tuple(spec.get("fillers", ())),
        filler_rate=filler_rate,
        typo_rate=typo_rate,
        ellipsis=bool(spec.get("ellipsis", False)),
        prompt=str(spec.get("prompt", "")),
        source=source,
    )


def load_humanizers(dirs: list[Path]) -> dict[str, Humanizer]:
    """Bundled humanizers overlaid with `humanizers*.yaml` from each library
    dir (later dirs override same-named entries — same semantics as the
    payload library)."""
    out: dict[str, Humanizer] = dict(BUNDLED)
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("humanizers*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise HumanizeError(f"{path}: expected a mapping of name -> spec")
            for name, spec in data.items():
                out[name] = _from_spec(name, spec or {}, str(path))
    return out
