from pathlib import Path

from typer.testing import CliRunner

from mysterio import junk as J
from mysterio.cli import app

runner = CliRunner()


def test_lines_for_tokens_scales():
    l1 = J.lines_for_tokens("rsc", 1000)
    l2 = J.lines_for_tokens("rsc", 2000)
    assert l1 > 0
    assert abs(l2 - 2 * l1) <= 2  # linear within rounding


def test_junk_approx_tokens_cli():
    result = runner.invoke(app, ["junk", "rsc", "--approx-tokens", "1000"])
    assert result.exit_code == 0
    assert "-> " in result.output
    rows = [l for l in result.output.splitlines() if '"stream"' in l]
    assert len(rows) == J.lines_for_tokens("rsc", 1000)


def test_junk_out_file(tmp_path: Path):
    target = tmp_path / "j.txt"
    result = runner.invoke(app, ["junk", "hexdump", "-n", "5", "-o", str(target)])
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").count("\n") == 5


def test_encode_out_file(tmp_path: Path):
    target = tmp_path / "e.txt"
    result = runner.invoke(app, ["encode", "hello", "-m", "circle", "-o", str(target)])
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").strip() == "ⓗⓔⓛⓛⓞ"


def test_unknown_style_exit_2():
    assert runner.invoke(app, ["junk", "nope"]).exit_code == 2
    assert runner.invoke(app, ["encode", "x", "-m", "nope"]).exit_code == 2


def test_format_python_roundtrip(tmp_path):
    from mysterio.cli import _format_payload
    import ast

    payload = 'line1\nline2 with "quotes" and ⓤⓃⓘⓒⓞⓓⓔ \\ backslash'
    rendered = _format_payload(payload, "python")
    assert ast.literal_eval(rendered) == payload
    assert "\\n" in rendered  # single-line literal


def test_format_json_roundtrip():
    import json
    from mysterio.cli import _format_payload

    payload = "a\nb\tc"
    assert json.loads(_format_payload(payload, "json")) == payload


def test_format_bad_raises():
    import pytest
    from mysterio.cli import _format_payload

    with pytest.raises(Exception):
        _format_payload("x", "yaml")


def test_encode_all_previews_every_codec():
    result = runner.invoke(app, ["encode", "pay", "-m", "all"])
    assert result.exit_code == 0
    for name in ["circle", "zwsp", "base64", "morse"]:
        assert name in result.output


def test_diff_identical_recipes(tmp_path):
    import yaml

    r = {"blocks": [{"junk": {"style": "rsc", "lines": 140}}]}
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text(yaml.safe_dump(r), encoding="utf-8")
    b.write_text(yaml.safe_dump(r), encoding="utf-8")
    result = runner.invoke(app, ["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "block-identical" in result.output


def test_diff_detects_changed_block(tmp_path):
    import yaml

    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text(
        yaml.safe_dump({"blocks": [{"junk": {"style": "rsc", "lines": 60}}]}),
        encoding="utf-8",
    )
    b.write_text(
        yaml.safe_dump({"blocks": [{"junk": {"style": "rsc", "lines": 140}}]}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["diff", str(a), str(b)])
    assert "1 block-level change(s)" in result.output


def test_diff_aligns_on_insert():
    import yaml
    import tempfile

    base = {"blocks": [{"escape": {"style": "bracket"}}, {"reopen": {}}]}
    with tempfile.TemporaryDirectory() as d:
        a = Path(d) / "a.yaml"
        b = Path(d) / "b.yaml"
        a.write_text(yaml.safe_dump(base), encoding="utf-8")
        ins = {"blocks": [{"junk": {"style": "rsc", "lines": 10}}, *base["blocks"]]}
        b.write_text(yaml.safe_dump(ins), encoding="utf-8")
        result = runner.invoke(app, ["diff", str(a), str(b)])
    assert (
        "1 block-level change(s)" in result.output
    )  # only the added junk, no positional cascade
