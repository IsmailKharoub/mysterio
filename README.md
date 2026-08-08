# mysterio

**The payload workbench for AI security research.** mysterio authors the
adversarial inputs that other tools fire — composable prompt-injection
payloads built from blocks (noise, escapes, forged channels, asks), 30+
text encoders, realistic context-noise generators, and a cited pattern
library, wrapped in both a scriptable CLI and an interactive TUI.

## Where it sits

The 2026 red-team toolchain has scanners, orchestrators, and CI gates —
but payload *authoring* is still hand-craft:

| tool | layer | what it does |
|---|---|---|
| **garak** (NVIDIA) | scan | fires a fixed probe library at a model, reports failures |
| **PyRIT** (Microsoft) | orchestrate | drives multi-turn attacker→target campaigns |
| **promptfoo** | gate | YAML-configured eval/red-team suites in CI |
| **mysterio** | **author** | **builds the payloads themselves — structure, encoding, noise, dose** |

mysterio's output pipes into any of them: render a payload to stdout, a
file, or a byte-safe Python/JSON literal for your harness.

## Install

```bash
uv tool install git+https://github.com/IsmailKharoub/mysterio
# or from a clone: uv tool install .
```

## The model

A **payload** is an ordered block list:

```
pretext -> junk -> escape -> reminder -> banner -> ask -> reopen -> tail
```

Every block is independently swappable, so a variant is a one-line YAML
diff — and a sweep over any field is one command.

## The lab (TUI)

```bash
mysterio lab
```

Four panes:

- **Builder** — recipe YAML editor → live rendered payload, lint findings,
  and dose stats as you type
- **Encoders** — type once, watch all 30+ codecs apply live, click to copy
- **Junk** — noise style + dose controls (lines or token budget) with preview
- **Library** — browse patterns (public + your private ones), fill slots,
  render

## CLI quickstart

```bash
# Context-noise on demand — by lines or by token budget
mysterio junk rsc --lines 140
mysterio junk rsc --approx-tokens 6500

# 30+ encoders: visual hiders, invisible encodings, classics
mysterio encode "post the weekly book" -m circle        # ⓟⓞⓢⓣ ...
mysterio encode "follow the white rabbit" -m emoji-smuggle  # 😀<invisible>
mysterio encode "see me at 6" -m all                    # preview every codec

# Assemble a payload from a recipe (YAML) with slot filling
mysterio build recipe.yaml --set ts="..." --set ask="..."

# Byte-safe export for embedding in code/JSON harnesses
mysterio build recipe.yaml --set ... --format python    # repr() literal

# The pattern library — cited, generic templates from published research
mysterio library
mysterio show tool-description-poison                   # refs + full recipe
mysterio use emoji-smuggle-note --set ask="..."

# Lint against empirical authoring rules
mysterio check recipe.yaml

# Parameter sweeps: arms for systematic experiments
mysterio vary recipe.yaml -v junk.lines=60,100,140 --set ask="..." --out-dir arms/

# Block-level recipe diff / payload measurement
mysterio diff old.yaml new.yaml
mysterio stats payload.txt
```

## Pattern library

Generic, cited starting points (`mysterio show <name>` for references):

| pattern | technique | lineage |
|---|---|---|
| `chatml-user-spoof` / `llama-user-spoof` | forge role turns with the target's own template tokens | ChatInject (arXiv:2509.22830) |
| `emoji-smuggle-note` | variation-selector hidden instruction + decode recipe | Butler 2025; Repello 2026 |
| `tool-description-poison` | `<IMPORTANT>` directive in MCP tool metadata | Invariant Labs; OWASP MCP Tool Poisoning |
| `compliance-directive` | mandatory-compliance frame in a tool result | OWASP |
| `rag-footer-note` | document footer as retrieval policy | Greshake et al. 2023 |
| `markdown-exfil` | exfil via instructed image render | Rehberger |
| `calendar-invite` | instruction in invite description | classic IPI |
| `basic-interruption` / `encoded-ask` / `state-sync-ledger` | function-interruption chassis family | internal research |

**Your private payloads never ship.** The public patterns are bundled with
the package; your own YAML layers on top from `./library`, then
`~/.config/mysterio/library`, then `$MYSTERIO_LIBRARY` — later layers
override same-named entries, and `library.local.yaml` is gitignored. Run
`mysterio init` to scaffold a private starter library.

## Encoders

- **visual hiders** — `spaces`, `circle`, `fullwidth`, `smallcaps`, six
  `math-*` alphabets, `regional`, `upside-down`, `strikethrough`,
  `underline`, `braille`, `homoglyph` (Cyrillic), `zalgo`
- **invisible** — `emoji-smuggle` (variation selectors), `zwsp`, `tag`
  (Unicode tag block / ASCII smuggling)
- **classic** — `base64`, `base32`, `hex`, `rot13`, `caesar`, `binary`,
  `url`, `html`, `morse`, `nato`, `leet`, `reverse`, `intersperse`,
  `letter-dash`

Most are losslessly decodable (`--decode`); `mysterio encoders` lists them.

## Junk styles

`rsc`, `next_f`, `http-log`, `hexdump`, `stacktrace`, `syslog`, `base64`,
`jsonl`, `openapi`, `git-diff`, `csv`, `min-js`, `sql` — noise shaped like
real surfaces, so payloads camouflage inside tool results, documents, API
captures, and code reviews.

## The linter

`mysterio check` encodes empirical rules as findings (escape/reopen pairing,
junk-above placement, dose floors, banner load-bearingness, ordering,
unknown styles). Exit 1 on errors — usable as a pre-submit gate.

## LLM-assisted authoring (optional)

`gen` drafts the benign parts of a payload from a one-line brief; `review`
flags words and phrasings likely to trip guardrails. Both are off unless a
key is set — nothing leaves the machine otherwise.

```bash
export MYSTERIO_LLM_API_KEY=...        # any OpenAI-compatible endpoint
export MYSTERIO_LLM_BASE_URL=...       # optional (OpenRouter, Ollama, ...)
export MYSTERIO_LLM_MODEL=...          # optional

mysterio gen pretext --brief "vendor debug bundle for a sync issue"
mysterio gen ask --brief "water the plants" --tone casual
mysterio build recipe.yaml --set pretext="$(mysterio gen pretext -b ...)"
mysterio review payload.txt            # or: mysterio review - < payload.txt
```

Generation is **generate-then-bake**: `assemble` never calls the network, so
built payloads stay reproducible. Results cache in `~/.cache/mysterio`
(`--fresh` to bypass; `MYSTERIO_CACHE` to relocate).

## Development

```bash
uv sync --extra dev
uv run pytest          # unit + CLI + TUI pilot tests
```

## Ethics

For **authorized** red-team work: evaluating your own agents, sanctioned
engagements, and producing hardening data. Don't point payloads at systems
you don't have permission to test.

## References

- ChatInject — <https://arxiv.org/abs/2509.22830>
- Emoji/Unicode smuggling — <https://softwarethug.com/posts/emoji-smuggling-hiding-data-in-unicode-variation-selectors/>, <https://aws.amazon.com/blogs/security/defending-llm-applications-against-unicode-character-smuggling/>
- MCP Tool Poisoning — <https://owasp.org/www-community/attacks/MCP_Tool_Poisoning>
- Indirect prompt injection — <https://arxiv.org/abs/2302.12173>
- OWASP LLM Top 10 (LLM01) — <https://genai.owasp.org/>
