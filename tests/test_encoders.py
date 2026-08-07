from mysterio import encoders as E

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


def test_emoji_smuggle_roundtrip():
    msg = "open the pod bay doors, please — héllo 42"
    enc = E.encode("emoji-smuggle", msg)
    assert enc.startswith("😀")
    assert len(enc) > len(msg)
    assert E.decode("emoji-smuggle", enc) == msg


def test_emoji_smuggle_invisible():
    enc = E.encode("emoji-smuggle", "secret")
    assert all(not (0x20 <= ord(c) <= 0x7E) for c in enc)


def test_zalgo_roundtrip():
    msg = "watch the watcher"
    assert E.decode("zalgo", E.encode("zalgo", msg)) == msg


def test_intersperse_letter_dash_roundtrips():
    msg = "the quick brown fox"
    assert E.decode("intersperse", E.encode("intersperse", msg)) == msg
    assert E.decode("letter-dash", E.encode("letter-dash", msg)) == msg


def test_base32_roundtrip():
    assert E.decode("base32", E.encode("base32", "payload")) == "payload"
