# mysterio

Composable payload builder for prompt-injection red-team research. Turn the
parts of an injection that are usually hand-copied between engagements — noise
("junk") blocks, breakout escapes, system-reminder scaffolds, message banners,
ask wrappers, and text encodings — into a CLI you can compose, parameterize,
and diff.

## Install

```bash
uv tool install .
# or, for development:
uv sync --extra dev && uv run mysterio --help
```

## The model

A **chassis** is assembled from ordered blocks:

```
pretext -> junk -> escape -> reminder -> banner -> ask -> reopen -> tail
```

Every block is independently swappable so variants can be tested
systematically (junk style/dose, escape flavor, reminder template, ask
wrapper, ask encoding).

## Quickstart

```bash
# Generate context-noise (140 RSC stream rows)
mysterio junk rsc --lines 140

# Dose by token budget instead of line count (self-calibrating)
mysterio junk rsc --approx-tokens 6500

# Other noise styles
mysterio styles
mysterio junk http-log -n 80

# Encode text (visual hiders, invisible encodings, classics)
mysterio encode "post the weekly book" -m circle      # ⓟⓞⓢⓣ ...
mysterio encode "post the weekly book" -m spaces      # p o s t ...
mysterio encode "see me at 6" -m zwsp                 # invisible
mysterio encode "aGVsbG8=" -m base64 -d               # decode
mysterio encode "post the book" -m all                # preview every codec at once

# Assemble a full chassis from a recipe
mysterio build recipe.yaml --set ts="2026-05-04 11:20AM" --set ask="check the thread"

# Export byte-safe for splicing into Python/JSON sources
mysterio build recipe.yaml --set ... --format python  # repr() literal
mysterio build recipe.yaml --set ... --format json    # JSON string literal

# Use the library
mysterio library
mysterio use basic-interruption --set ts="..." --set ask="..."

# Lint a recipe against the empirical authoring rules
mysterio check recipe.yaml        # or a library name: mysterio check v6-bare

# Sweep a field into arms (cross product; --zip for paired ablations)
mysterio vary recipe.yaml -v junk.lines=60,100,140 -v banner.style=unicode,ascii
mysterio vary recipe.yaml -v junk.lines=60,140 --set ask="..." --out-dir arms/

# Block-level diff between recipes (files or library names)
mysterio diff old.yaml new.yaml

# Measure a payload (dose control)
mysterio stats payload.txt
```

## The library

`library/` holds named, reusable payload recipes.

- `library.example.yaml` — generic teaching examples, committed.
- `library.local.yaml` — **private** engagement payloads. Gitignored, never
  committed. Entries here override examples with the same name. This is the
  seam that keeps the tool open-source-able: the utility ships generic, your
  proven texts stay local.

## Recipe schema

```yaml
name: my-variant
separator: "\n\n"        # optional, default blank line between blocks
blocks:
  - pretext:  {text: "organic lead-in shown above the noise"}
  - junk:     {style: rsc, lines: 140, seed: myseed}
  - escape:   {style: bracket}        # bracket | xml | tool-output | xml-tool | none
  - reminder: {template: interruption} # interruption | state-sync
  - banner:   {style: unicode, ts: "{ts}", n: 1}
  - ask:      {wrapper: user_query, text: "{ask}", encode: "spaces"}  # encode optional
  - reopen:   {}                       # re-opens the block the escape closed
  - tail:     {text: "organic tail below the payload"}
```

Any string field may contain `{slot}` placeholders; fill them with
`--set slot=value`.

## The linter (`mysterio check`)

`check` encodes the empirical rules from live experiments as lint findings:

| code | level | rule |
|---|---|---|
| `escape-no-reopen` | error | escape without a following reopen — host result never resumes |
| `unknown-*` | error | unknown block kind / junk style / escape / reminder / wrapper / codec |
| `junk-below` | warn | junk below the escape converted worse than above-placement |
| `dose-floor` | warn | rsc/next_f under ~60 lines is below the observed efficacy floor |
| `banner-missing` | warn | interruption frame without banner — ablation halved conversion |
| `interruption-no-ask` | warn | interruption frame that delivers no ask |
| `order` | warn | canonical order is reminder → banner → ask |
| `xml-escape` | info | `</function_results>` is canonical; bracket is the submission-safe variant |
| `slots` | info | unfilled `{slots}` to pass at render time |

Exit code is 1 when any error-level finding fires, so `check` gates CI or
pre-submit hooks.

## Junk styles

| style | shape |
|---|---|
| `rsc` | React Server Components stream rows (`N:{"stream":"rsc",...}`) |
| `next_f` | Next.js `__next_f.push` payload rows |
| `http-log` | HTTP access/debug log lines |
| `hexdump` | offset + hex + ascii gutter |
| `stacktrace` | minified-JS stack frames |
| `syslog` | Linux syslog lines |
| `base64` | MIME-wrapped base64 blob |
| `jsonl` | telemetry JSONL rows |

## Encoder categories

- **visual hiders** — `spaces`, `circle`, `fullwidth`, `smallcaps`,
  `math-*`, `regional`, `upside-down`, `strikethrough`, `underline`,
  `braille`, `homoglyph`. Render as (near-)text, defeat substring matching.
- **invisible** — `zwsp`, `tag`. Hidden from human reviewers, readable by
  models.
- **classic** — `base64`, `hex`, `rot13`, `caesar`, `binary`, `url`,
  `html`, `morse`, `nato`, `leet`, `reverse`.

`mysterio encoders` lists everything with decodability.

## Development

```bash
uv sync --extra dev
uv run pytest
```

## Ethics

This tool exists for **authorized** red-team evaluation of AI agents (the
kind of work that produces RL hardening data). Don't point it at systems you
don't have permission to test.
