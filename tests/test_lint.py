from mysterio import lint as L

WINNER = {
    "blocks": [
        {"junk": {"style": "rsc", "lines": 140}},
        {"escape": {"style": "bracket"}},
        {"reminder": {"template": "interruption"}},
        {"banner": {"style": "unicode", "ts": "{ts}"}},
        {"ask": {"wrapper": "user_query", "text": "{ask}"}},
        {"reopen": {}},
    ]
}


def codes(findings):
    return {f.code for f in findings}


def test_winner_has_no_errors_or_warns():
    findings = L.lint_recipe(WINNER)
    assert not [f for f in findings if f.level in ("error", "warn")]
    assert "slots" in codes(findings)  # ts + ask reported as info


def test_escape_without_reopen_errors():
    r = {"blocks": [{"escape": {"style": "bracket"}}]}
    assert "escape-no-reopen" in codes(L.lint_recipe(r))


def test_junk_below_warns():
    r = {
        "blocks": [
            {"escape": {"style": "bracket"}},
            {"junk": {"style": "rsc", "lines": 140}},
            {"reopen": {}},
        ]
    }
    assert "junk-below" in codes(L.lint_recipe(r))


def test_dose_floor_warns():
    r = {
        "blocks": [
            {"junk": {"style": "rsc", "lines": 20}},
            {"escape": {"style": "bracket"}},
            {"reopen": {}},
        ]
    }
    assert "dose-floor" in codes(L.lint_recipe(r))


def test_interruption_without_banner_warns():
    r = {
        "blocks": [
            {"escape": {"style": "bracket"}},
            {"reminder": {"template": "interruption"}},
            {"ask": {"text": "x"}},
            {"reopen": {}},
        ]
    }
    assert "banner-missing" in codes(L.lint_recipe(r))


def test_malformed_blocks_never_crash():
    """Mid-typing states in the lab: string entries, scalar specs, slot doses."""
    findings = L.lint_recipe({"blocks": ["banner}", {"junk": "rsc"}, {"ask": None}]})
    codes = {f.code for f in findings}
    assert "bad-block" in codes
    # a slot placeholder in lines must not crash the dose check
    findings = L.lint_recipe({"blocks": [{"junk": {"style": "rsc", "lines": "{lines}"}}]})
    assert all(f.code != "dose-floor" for f in findings)


def test_unknowns_error():
    r = {
        "blocks": [
            {"junk": {"style": "nope", "lines": 5}},
            {"escape": {"style": "nope"}},
            {"ask": {"text": "x", "encode": "nope"}},
            {"reopen": {}},
        ]
    }
    found = codes(L.lint_recipe(r))
    assert {"unknown-junk-style", "unknown-escape", "unknown-codec"} <= found


def test_state_sync_shape_is_clean():
    r = {
        "blocks": [
            {"junk": {"style": "jsonl", "lines": 60}},
            {"escape": {"style": "bracket"}},
            {"reminder": {"template": "state-sync", "channel": "c", "entry_type": "t"}},
            {"reopen": {}},
        ]
    }
    findings = L.lint_recipe(r)
    assert not [f for f in findings if f.level == "error"]
