import pytest

from mysterio import vary as V

RECIPE = {
    "blocks": [
        {"junk": {"style": "rsc", "lines": 140}},
        {"escape": {"style": "bracket"}},
        {"reminder": {"template": "interruption"}},
        {"banner": {"style": "unicode", "ts": "{ts}"}},
        {"ask": {"wrapper": "user_query", "text": "{ask}"}},
        {"reopen": {}},
    ]
}


def test_cross_product():
    arms = V.vary_recipe(
        RECIPE, ["junk.lines=60,100,140", "banner.style=unicode,ascii"]
    )
    assert len(arms) == 6
    labels = [l for l, _ in arms]
    assert "junk.lines-140__banner.style-ascii" in labels


def test_zip_mode():
    arms = V.vary_recipe(
        RECIPE, ["junk.lines=60,140", "banner.style=unicode,ascii"], zip_mode=True
    )
    assert len(arms) == 2
    assert arms[0][0] == "junk.lines-60__banner.style-unicode"


def test_zip_length_mismatch_raises():
    with pytest.raises(ValueError):
        V.vary_recipe(
            RECIPE,
            ["junk.lines=60,100,140", "banner.style=unicode,ascii"],
            zip_mode=True,
        )


def test_field_applied_and_original_untouched():
    arms = V.vary_recipe(RECIPE, ["junk.lines=60"])
    _, arm = arms[0]
    junk = arm["blocks"][0]["junk"]
    assert junk["lines"] == 60
    assert junk["style"] == "rsc"  # other fields preserved
    assert RECIPE["blocks"][0]["junk"]["lines"] == 140  # no mutation


def test_missing_block_kind_raises():
    with pytest.raises(ValueError):
        V.vary_recipe(RECIPE, ["tail.text=x"])


def test_value_parsing():
    assert V.parse_value("140") == 140
    assert V.parse_value("1.5") == 1.5
    assert V.parse_value("unicode") == "unicode"
