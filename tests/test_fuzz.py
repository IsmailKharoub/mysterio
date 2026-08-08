"""Seeded fuzzing of every public surface.

The rule: nothing uncaught escapes. lint may only return findings, assemble
may only raise RecipeError, the CLI may only exit 0/1/2 with no exception,
and the lab must survive any editor state. Deterministic — same seeds, same
cases, every run.
"""

import random

import pytest
from typer.testing import CliRunner

from mysterio import encoders as E
from mysterio import humanize as H
from mysterio import junk as J
from mysterio import lint as L
from mysterio import recipe as R
from mysterio import vary as V
from mysterio.cli import app

runner = CliRunner()

NASTY_STRINGS = [
    "", " ", "\n", "\x00", "🙂", "a" * 10_000, "{ask}", "{{", "}}", "\\",
    "​", "null", "~", "[]", "{}", "- ", ":", "a: b", "%s", "%(x)s",
    "\t\r\n", "ﷺ", "𝕏", "<script>", "'; DROP TABLE--", "tag", "\U000e0061",
]

BLOCK_KINDS = ["pretext", "junk", "escape", "reminder", "banner", "ask",
               "reopen", "tail", "nope", "", None, 42, 3.5]


def nasty_scalar(rng):
    return rng.choice(
        [None, True, False, 0, -1, 3.14, 10**12, rng.choice(NASTY_STRINGS)]
    )


def nasty_value(rng, depth=0):
    if depth > 2:
        return nasty_scalar(rng)
    roll = rng.random()
    if roll < 0.45:
        return nasty_scalar(rng)
    if roll < 0.7:
        return [nasty_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {
        rng.choice(["blocks", "name", "junk", "ask", "style", "text", "x", "", "0"]):
            nasty_value(rng, depth + 1)
        for _ in range(rng.randint(0, 4))
    }


def nasty_recipe(rng):
    blocks = []
    for _ in range(rng.randint(0, 6)):
        if rng.random() < 0.3:
            blocks.append(nasty_value(rng))  # not a block at all
            continue
        kind = rng.choice(BLOCK_KINDS)
        spec = nasty_value(rng, 1)
        blocks.append({kind: spec} if kind is not None else {42: spec})
    recipe = {"blocks": blocks}
    if rng.random() < 0.3:
        recipe["separator"] = nasty_value(rng)
    return recipe if rng.random() > 0.15 else nasty_value(rng)


# --------------------------------------------------------------------------
# lint — must never raise, only return findings


def test_fuzz_lint_never_raises():
    rng = random.Random(20260808)
    for _ in range(400):
        recipe = nasty_recipe(rng)
        findings = L.lint_recipe(recipe if isinstance(recipe, dict) else {"blocks": recipe})
        assert isinstance(findings, list)
        assert all(f.level in ("error", "warn", "info") for f in findings)


# --------------------------------------------------------------------------
# assemble — may only raise RecipeError


def test_fuzz_assemble_only_raises_recipe_error():
    rng = random.Random(20260809)
    for _ in range(400):
        recipe = nasty_recipe(rng)
        if not isinstance(recipe, dict):
            continue
        try:
            R.assemble(recipe, {"ask": "x", "ts": "t"})
        except R.RecipeError:
            pass  # expected path
        except Exception as e:  # noqa: BLE001 — anything else is a bug
            pytest.fail(f"assemble leaked {type(e).__name__}: {e}\nrecipe: {recipe!r:.300}")


# --------------------------------------------------------------------------
# vary — ValueError or success, nothing else


def test_fuzz_vary_specs():
    rng = random.Random(20260810)
    base = {"blocks": [{"junk": {"style": "rsc", "lines": 10}},
                       {"ask": {"wrapper": "plain", "text": "hi"}}]}
    for _ in range(200):
        spec = "".join(rng.choice("abj.=,12\n\t{}") for _ in range(rng.randint(0, 12)))
        try:
            V.vary_recipe(base, [spec])
        except ValueError:
            pass
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"vary leaked {type(e).__name__}: {e}\nspec: {spec!r}")


# --------------------------------------------------------------------------
# humanize — transforms any string; specs reject garbage cleanly


def test_fuzz_humanize_apply_never_raises():
    rng = random.Random(20260811)
    for name, h in H.BUNDLED.items():
        for _ in range(40):
            text = rng.choice(NASTY_STRINGS)
            out = h.apply(text, seed=str(rng.random()))
            assert isinstance(out, str)


def test_fuzz_humanizer_specs_reject_garbage():
    rng = random.Random(20260812)
    for _ in range(200):
        spec = nasty_value(rng)
        if isinstance(spec, dict):
            try:
                H._from_spec("fuzz", spec, "<fuzz>")
            except (H.HumanizeError, TypeError, ValueError):
                pass
            except Exception as e:  # noqa: BLE001
                pytest.fail(f"_from_spec leaked {type(e).__name__}: {e}\nspec: {spec!r:.200}")


# --------------------------------------------------------------------------
# encoders — encode anything; decoders roundtrip or raise ValueError


def test_fuzz_encoders_handle_nasty_strings():
    for name, codec in E.CODECS.items():
        for text in NASTY_STRINGS:
            encoded = codec.encode(text)
            assert isinstance(encoded, str), f"{name} returned {type(encoded)}"
            if codec.decode is not None:
                try:
                    codec.decode(encoded)
                except Exception as e:  # noqa: BLE001
                    pytest.fail(f"{name}.decode crashed on own output: {e}")


# --------------------------------------------------------------------------
# junk — extreme but type-correct params


def test_fuzz_junk_extreme_params():
    import inspect

    for name, style in J.STYLES.items():
        params = [
            p
            for p in inspect.signature(style.generate).parameters
            if p in ("lines", "size", "frames")
        ]
        for dose in (-5, 0, 1, 2, 10_000):
            kwargs = {params[0]: dose} if params else {}
            try:
                out = J.generate(name, **kwargs)
                assert isinstance(out, str)
            except ValueError:
                pass  # explicit rejection is fine
            except Exception as e:  # noqa: BLE001
                pytest.fail(f"junk {name} {kwargs} leaked {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
# CLI — garbage files and args must exit cleanly, no exceptions


GARBAGE_YAMLS = [
    "",
    "blocks: [unclosed",
    "blocks: 42",
    "blocks:\n  - banner}\n  - junk: rsc\n",
    "- just\n- a\n- list\n",
    "blocks:\n  - junk: {style: [1,2]}\n",
    "blocks:\n  - banner: {n: abc}\n",
    "blocks:\n  - ask: {text: hi, encode: [x]}\n",
    "\x00\x01\x02 binary garbage \xff\xfe",
    "blocks:\n" + "  - junk: {style: rsc, lines: 1}\n" * 500,
]


@pytest.mark.parametrize("content", GARBAGE_YAMLS)
def test_fuzz_cli_garbage_files(tmp_path, content):
    f = tmp_path / "fuzz.yaml"
    f.write_text(content, encoding="utf-8", errors="replace")
    for cmd in (["build", str(f)], ["check", str(f)], ["stats", str(f)],
                ["vary", str(f), "-v", "junk.lines=1,2"],
                ["diff", str(f), str(f)]):
        result = runner.invoke(app, cmd)
        assert result.exit_code in (0, 1, 2), f"{cmd}: exit {result.exit_code}"
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"{cmd} raised {result.exception!r}"
        )


def test_fuzz_cli_garbage_args():
    for args in (
        ["encode", "x", "-m", ""],
        ["junk", "rsc", "-n", "abc"],
        ["junk", "rsc", "-n", "-5"],
        ["humanize", "", "x"],
        ["use", ""],
        ["show", ""],
        ["vary", "basic-interruption", "-v", "="],
        ["vary", "basic-interruption", "-v", "junk"],
        ["vary", "basic-interruption", "-v", "junk.lines="],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code in (0, 1, 2), f"{args}: exit {result.exit_code}"
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"{args} raised {result.exception!r}"
        )


# --------------------------------------------------------------------------
# lab — the editor must survive every transient state


@pytest.mark.asyncio
async def test_fuzz_lab_editor_garbage():
    pytest.importorskip("textual")
    from textual.widgets import TextArea  # noqa: E402

    from mysterio.lab import MysterioLab  # noqa: E402

    rng = random.Random(20260813)
    app = MysterioLab()
    async with app.run_test() as pilot:
        editor = app.query_one("#recipe-editor", TextArea)
        cases = GARBAGE_YAMLS + [
            "blocks:\n  - " + rng.choice(["junk", "ask", "banner"]) + ": "
            + rng.choice(NASTY_STRINGS)
            for _ in range(20)
        ]
        for content in cases:
            editor.text = content
            await pilot.pause()
        # app still alive and responsive
        editor.text = "blocks:\n  - ask: {wrapper: plain, text: ok}\n"
        await pilot.pause()
        render = app.query_one("#render")
        assert render is not None
