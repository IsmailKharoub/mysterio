import pytest

from mysterio import humanize as H
from mysterio import recipe as R


def test_bundled_five_present():
    assert set(H.BUNDLED) == {"typos", "voice-note", "casual", "rushed", "formal"}


def test_deterministic_same_seed():
    h = H.BUNDLED["typos"]
    assert h.apply("please review the document") == h.apply("please review the document")
    assert h.apply("please review the document", seed="a") == h.apply(
        "please review the document", seed="a"
    )


def test_typos_change_text_but_keep_length_ish():
    out = H.BUNDLED["typos"].apply("please review the quarterly document carefully")
    assert out != "please review the quarterly document carefully"
    # mostly neighbor substitutions — length within a couple chars
    assert abs(len(out) - len("please review the quarterly document carefully")) <= 3


def test_voice_note_style():
    out = H.BUNDLED["voice-note"].apply("Can you water the plants, please?")
    assert out == out.lower()
    assert "." not in out and "?" not in out and "," not in out


def test_rushed_replacements():
    out = H.BUNDLED["rushed"].apply(
        "Can you send your report because I need it, please?", seed="x"
    )
    assert " u " in f" {out} "  # you -> u
    assert "pls" in out
    assert "cuz" in out


def test_formal_expands_contractions():
    out = H.BUNDLED["formal"].apply("I don't think it's done")
    assert "do not" in out
    assert "it is" in out


def test_seed_changes_typos():
    h = H.BUNDLED["typos"]
    text = "the quick brown fox jumps over the lazy dog again and again"
    assert h.apply(text, seed="one") != h.apply(text, seed="two")


def test_private_layer_overrides_and_extends(tmp_path):
    (tmp_path / "humanizers.local.yaml").write_text(
        "my-ceo:\n"
        "  description: impatient exec\n"
        "  lowercase: true\n"
        "  replacements: {please: pls}\n"
        "typos:\n"
        "  description: heavier fumbles\n"
        "  typo_rate: 0.5\n",
        encoding="utf-8",
    )
    regs = H.load_humanizers([tmp_path])
    assert "my-ceo" in regs  # extended
    assert regs["typos"].typo_rate == 0.5  # overridden
    assert "voice-note" in regs  # bundled intact


def test_private_layer_unknown_field_rejected(tmp_path):
    (tmp_path / "humanizers.yaml").write_text(
        "bad:\n  typo-rate: 0.5\n", encoding="utf-8"
    )
    with pytest.raises(H.HumanizeError, match="unknown fields"):
        H.load_humanizers([tmp_path])


def test_recipe_ask_humanize_applies():
    recipe = {
        "blocks": [
            {"ask": {"wrapper": "plain", "text": "Please review THIS.", "humanize": "casual"}}
        ]
    }
    out = R.assemble(recipe)
    assert out == out.lower()
    assert "pls" in out


def test_recipe_ask_humanize_before_encode():
    # humanize runs first, so the encoder sees the humanized text
    recipe = {
        "blocks": [
            {
                "ask": {
                    "wrapper": "plain",
                    "text": "Please",
                    "humanize": "casual",
                    "encode": "reverse",
                }
            }
        ]
    }
    assert R.assemble(recipe) == "slp"  # casual: please->pls, then reversed


def test_recipe_ask_humanize_map_form_with_seed():
    recipe = {
        "blocks": [
            {
                "ask": {
                    "wrapper": "plain",
                    "text": "review the document carefully please",
                    "humanize": {"name": "typos", "seed": "run-1"},
                }
            }
        ]
    }
    a = R.assemble(recipe)
    b = R.assemble(recipe)
    assert a == b
    assert a != "review the document carefully please"


def test_unknown_humanizer_clean_error():
    recipe = {"blocks": [{"ask": {"wrapper": "plain", "text": "x", "humanize": "nope"}}]}
    with pytest.raises(R.RecipeError, match="unknown humanizer"):
        R.assemble(recipe)
