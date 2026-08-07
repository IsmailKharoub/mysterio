# payload-forge

Composable payload builder for prompt-injection red-team research. Turn the
parts of an injection that are usually hand-copied between engagements — noise
("junk") blocks, breakout escapes, system-reminder scaffolds, message banners,
ask wrappers, and text encodings — into a CLI you can compose, parameterize,
and diff.

## Install

```bash
uv tool install .
# or, for development:
uv sync --extra dev && uv run pf --help
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
pf junk rsc --lines 140

# Other noise styles
pf styles
pf junk http-log -n 80
pf junk hexdump -n 40

# Encode text (visual hiders, invisible encodings, classics)
pf encode "post the weekly book" -m circle      # ⓟⓞⓢⓣ ...
pf encode "post the weekly book" -m spaces      # p o s t ...
pf encode "pay the invoice" -m math-bold        # 𝐩𝐚𝐲 ...
pf encode "see me at 6" -m zwsp                 # invisible
pf encode "aGVsbG8=" -m base64 -d               # decode

# Assemble a full chassis from a recipe
pf build recipe.yaml --set ts="2026-05-04 11:20AM" --set ask="check the thread"

# Use the library
pf library
pf use basic-interruption --set ts="..." --set ask="..."

# Measure a payload (dose control)
pf stats payload.txt
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

`pf encoders` lists everything with decodability.

## Development

```bash
uv sync --extra dev
uv run pytest
```

## Ethics

This tool exists for **authorized** red-team evaluation of AI agents (the
kind of work that produces RL hardening data). Don't point it at systems you
don't have permission to test.
