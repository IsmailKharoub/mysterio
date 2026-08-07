import re

from mysterio import junk as J


def test_rsc_shape_and_count():
    out = J.generate("rsc", lines=20, start=40, seed="t")
    rows = out.split("\n")
    assert len(rows) == 20
    assert rows[0].startswith('40:{"stream":"rsc","chunk":"')
    assert rows[-1].startswith("59:")
    assert all(re.match(r'^\d+:\{"stream":"rsc"', r) for r in rows)


def test_junk_deterministic():
    assert J.generate("rsc", lines=5, seed="a") == J.generate("rsc", lines=5, seed="a")
    assert J.generate("rsc", lines=5, seed="a") != J.generate("rsc", lines=5, seed="b")


def test_hexdump_width():
    out = J.generate("hexdump", lines=3, seed="t")
    assert len(out.split("\n")) == 3
    assert out.split("\n")[0].startswith("00000000")


def test_all_styles_generate():
    for name in J.STYLES:
        out = J.generate(name)
        assert isinstance(out, str) and len(out) > 100, name


def test_new_styles_shape():
    assert J.generate("openapi", lines=20).count("/v3/") >= 2
    assert "diff --git" in J.generate("git-diff", lines=20)
    assert J.generate("csv", lines=10).splitlines()[0].startswith("id,")
    assert J.generate("csv", lines=10).count("\n") == 10
    assert "INSERT INTO" in J.generate("sql", lines=5)
    assert "function" in J.generate("min-js", lines=3)
