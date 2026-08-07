from payload_forge import encoders as E

SAMPLE = "post the book by 6pm"


def test_roundtrips():
    for name in [
        "spaces",
        "circle",
        "fullwidth",
        "smallcaps",
        "math-bold",
        "upside-down",
        "base64",
        "hex",
        "rot13",
        "caesar",
        "binary",
        "url",
        "html",
        "morse",
        "reverse",
        "zwsp",
        "tag",
    ]:
        enc = E.encode(name, SAMPLE)
        assert enc != SAMPLE, name
        assert (
            E.decode(name, enc) == SAMPLE.lower()
            if name == "tag"
            else E.decode(name, enc) == SAMPLE
        ), name


def test_circle_renders():
    assert E.encode("circle", "abc") == "ⓐⓑⓒ"


def test_spaces_three_space_word_gap():
    out = E.encode("spaces", "ab cd")
    assert out == "a b   c d"


def test_homoglyph_not_ascii():
    out = E.encode("homoglyph", "ace")
    assert out != "ace"
    assert len(out) == 3


def test_zwsp_invisible_count():
    out = E.encode("zwsp", "ab")
    assert out.count("​") == 1


def test_regional():
    assert "🇵" in E.encode("regional", "payload")


def test_unknown_codec_raises():
    try:
        E.encode("nope", "x")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_not_decodable_raises():
    try:
        E.decode("homoglyph", "x")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
