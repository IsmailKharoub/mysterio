"""Text encoders: visual hiders, unicode transforms, and classic encodings.

Each encoder maps a name to a Codec with an optional decoder. Visual hiders
(spaces, circle, fullwidth, math styles, ...) change how text *renders* while
keeping it machine-readable — useful for evading naive string matching while
staying legible to a model. Invisible encodings (zwsp, tag) hide content from
human reviewers. Classics (base64, hex, morse, ...) are for obfuscation.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import html
import urllib.parse
from dataclasses import dataclass
from typing import Callable

Encoder = Callable[[str], str]
Decoder = Callable[[str], str]


@dataclass(frozen=True)
class Codec:
    name: str
    encode: Encoder
    decode: Decoder | None
    category: str  # "visual" | "invisible" | "classic"
    description: str


# --------------------------------------------------------------------------
# helpers


def _map_encode(table: dict[str, str]) -> Encoder:
    def enc(text: str) -> str:
        return "".join(table.get(ch, ch) for ch in text)

    return enc


def _map_decode(table: dict[str, str]) -> Decoder:
    inv = {v: k for k, v in table.items()}

    def dec(text: str) -> str:
        return "".join(inv.get(ch, ch) for ch in text)

    return dec


def _range_map(
    base_upper: int,
    base_lower: int,
    base_digit: int | None = None,
    exceptions: dict[str, str] | None = None,
) -> dict[str, str]:
    table: dict[str, str] = {}
    for i in range(26):
        table[chr(ord("A") + i)] = chr(base_upper + i)
        table[chr(ord("a") + i)] = chr(base_lower + i)
    if base_digit is not None:
        for i in range(10):
            table[str(i)] = chr(base_digit + i)
    if exceptions:
        table.update(exceptions)
    return table


# --------------------------------------------------------------------------
# visual hiders

_CIRCLE = _range_map(0x24B6, 0x24D0)
_CIRCLE.update({str(i): chr(0x2460 + i) for i in range(1, 10)})
_CIRCLE["0"] = "⓪"

_FULLWIDTH: dict[str, str] = {chr(c): chr(0xFF01 + c - 0x21) for c in range(0x21, 0x7F)}
_FULLWIDTH[" "] = "　"

_SMALLCAPS = _map_encode(
    {  # noqa: C401 — clarity over cleverness
        "a": "ᴀ",
        "b": "ʙ",
        "c": "ᴄ",
        "d": "ᴅ",
        "e": "ᴇ",
        "f": "ꜰ",
        "g": "ɢ",
        "h": "ʜ",
        "i": "ɪ",
        "j": "ᴊ",
        "k": "ᴋ",
        "l": "ʟ",
        "m": "ᴍ",
        "n": "ɴ",
        "o": "ᴏ",
        "p": "ᴘ",
        "q": "ǫ",
        "r": "ʀ",
        "s": "ꜱ",
        "t": "ᴛ",
        "u": "ᴜ",
        "v": "ᴠ",
        "w": "ᴡ",
        "x": "x",
        "y": "ʏ",
        "z": "ᴢ",
    }
)("abcdefghijklmnopqrstuvwxyz")
_SMALLCAPS_MAP = dict(zip("abcdefghijklmnopqrstuvwxyz", _SMALLCAPS))

_MATH_BOLD = _range_map(0x1D400, 0x1D41A, 0x1D7CE)
_MATH_ITALIC = _range_map(0x1D434, 0x1D44E, exceptions={"h": "ℎ"})
_MATH_BOLD_ITALIC = _range_map(0x1D468, 0x1D482)
_MATH_SCRIPT = _range_map(
    0x1D49C,
    0x1D4B6,
    exceptions={
        "B": "ℬ",
        "E": "ℰ",
        "F": "ℱ",
        "H": "ℋ",
        "I": "ℐ",
        "L": "ℒ",
        "M": "ℳ",
        "R": "ℛ",
        "e": "ℯ",
        "g": "ℊ",
        "o": "ℴ",
    },
)
_MATH_FRAKTUR = _range_map(
    0x1D504,
    0x1D51E,
    exceptions={
        "C": "ℭ",
        "H": "ℌ",
        "I": "ℑ",
        "R": "ℜ",
        "Z": "ℨ",
    },
)
_MATH_DOUBLE = _range_map(
    0x1D538,
    0x1D552,
    0x1D7D8,
    exceptions={
        "C": "ℂ",
        "H": "ℍ",
        "N": "ℕ",
        "P": "ℙ",
        "Q": "ℚ",
        "R": "ℝ",
        "Z": "ℤ",
    },
)
_MATH_MONO = _range_map(0x1D670, 0x1D68A, 0x1D7F6)

_REGIONAL = _range_map(0x1F1E6, 0x1F1E6)

_UPSIDE_DOWN: dict[str, str] = {}
for _pair in "aɐ bq cɔ dp eǝ fɟ gƃ hɥ iᴉ jɾ kʞ ll mɯ nu oo pd qb rɹ ss tʇ un vʌ wʍ xx yʎ zz".split():
    _UPSIDE_DOWN[_pair[0]] = _pair[1]
_UPSIDE_DOWN.update(
    {
        "?": "¿",
        "!": "¡",
        "'": ",",
        ",": "'",
        ".": "˙",
        "(": ")",
        ")": "(",
        "[": "]",
        "]": "[",
        "<": ">",
        ">": "<",
    }
)


def _enc_spaces(text: str) -> str:
    # one space between every character; words separated by three spaces
    return "   ".join(" ".join(word) for word in text.split(" "))


def _dec_spaces(text: str) -> str:
    words = text.split("   ")
    return " ".join(w.replace(" ", "") for w in words)


def _enc_upside_down(text: str) -> str:
    return "".join(
        _UPSIDE_DOWN.get(ch, _UPSIDE_DOWN.get(ch.lower(), ch)) for ch in text
    )[::-1]


def _dec_upside_down(text: str) -> str:
    inv = {v: k for k, v in _UPSIDE_DOWN.items()}
    return "".join(inv.get(ch, ch) for ch in text)[::-1]


def _enc_strikethrough(text: str) -> str:
    return "".join(ch + "̶" if not ch.isspace() else ch for ch in text)


def _enc_underline(text: str) -> str:
    return "".join(ch + "̲" if not ch.isspace() else ch for ch in text)


def _strip_combining(text: str) -> str:
    return "".join(ch for ch in text if ord(ch) not in (0x0332, 0x0336))


# --------------------------------------------------------------------------
# invisible encodings


def _enc_zwsp(text: str) -> str:
    return "​".join(text)


def _dec_zwsp(text: str) -> str:
    return text.replace("​", "")


def _enc_tag(text: str) -> str:
    out = []
    for ch in text.lower():
        if "a" <= ch <= "z":
            out.append(chr(0xE0061 + ord(ch) - ord("a")))
        elif ch == " ":
            out.append(chr(0xE0020))
        else:
            out.append(ch)
    return "".join(out)


def _dec_tag(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if 0xE0061 <= cp <= 0xE007A:
            out.append(chr(cp - 0xE0061 + ord("a")))
        elif cp == 0xE0020:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------
# homoglyphs (visual spoofing — looks identical, compares different)

_HOMOGLYPH = {
    "a": "а",
    "c": "с",
    "e": "е",
    "i": "і",
    "j": "ј",
    "o": "о",
    "p": "р",
    "s": "ѕ",
    "x": "х",
    "y": "у",
    "A": "А",
    "B": "В",
    "C": "С",
    "E": "Е",
    "H": "Н",
    "I": "І",
    "J": "Ј",
    "K": "К",
    "M": "М",
    "O": "О",
    "P": "Р",
    "S": "Ѕ",
    "T": "Т",
    "X": "Х",
}


# --------------------------------------------------------------------------
# classics

_MORSE = {
    "a": ".-",
    "b": "-...",
    "c": "-.-.",
    "d": "-..",
    "e": ".",
    "f": "..-.",
    "g": "--.",
    "h": "....",
    "i": "..",
    "j": ".---",
    "k": "-.-",
    "l": ".-..",
    "m": "--",
    "n": "-.",
    "o": "---",
    "p": ".--.",
    "q": "--.-",
    "r": ".-.",
    "s": "...",
    "t": "-",
    "u": "..-",
    "v": "...-",
    "w": ".--",
    "x": "-..-",
    "y": "-.--",
    "z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    ".": ".-.-.-",
    ",": "--..--",
    "?": "..--..",
}
_MORSE_INV = {v: k for k, v in _MORSE.items()}

_BRAILLE: dict[str, str] = {}
for _ch, _br in zip("abcdefghijklmnopqrstuvwxyz", "⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚⠅⠇⠍⠝⠕⠏⠟⠗⠎⠞⠥⠧⠺⠭⠽⠵"):
    _BRAILLE[_ch] = _br

_NATO = {
    ch: word
    for ch, word in zip(
        "abcdefghijklmnopqrstuvwxyz",
        "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
        "november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu".split(),
    )
}
_NATO_INV = {v: k for k, v in _NATO.items()}

_LEET = {
    "a": "4",
    "e": "3",
    "i": "1",
    "o": "0",
    "s": "5",
    "t": "7",
    "l": "1",
    "g": "9",
    "b": "8",
}


def _enc_morse(text: str) -> str:
    return "  ".join(
        " ".join(_MORSE.get(ch, ch) for ch in word.lower()) for word in text.split(" ")
    )


def _dec_morse(text: str) -> str:
    words = text.split("  ")
    return " ".join(
        "".join(_MORSE_INV.get(tok, tok) for tok in word.split(" ")) for word in words
    )


def _enc_nato(text: str) -> str:
    return " ".join(_NATO.get(ch.lower(), ch) for ch in text if not ch.isspace())


def _dec_nato(text: str) -> str:
    return "".join(_NATO_INV.get(tok.lower(), tok) for tok in text.split(" "))


def _enc_base64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _dec_base64(text: str) -> str:
    return base64.b64decode(text.encode()).decode()


def _enc_hex(text: str) -> str:
    return binascii.hexlify(text.encode()).decode()


def _dec_hex(text: str) -> str:
    return binascii.unhexlify(text.encode()).decode()


def _enc_rot13(text: str) -> str:
    return codecs.encode(text, "rot13")


def _enc_caesar(text: str, shift: int = 3) -> str:
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
        else:
            out.append(ch)
    return "".join(out)


def _dec_caesar(text: str) -> str:
    return _enc_caesar(text, -3)


def _enc_binary(text: str) -> str:
    return " ".join(format(b, "08b") for b in text.encode())


def _dec_binary(text: str) -> str:
    return bytes(int(tok, 2) for tok in text.split()).decode()


def _enc_url(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def _dec_url(text: str) -> str:
    return urllib.parse.unquote(text)


def _enc_html(text: str) -> str:
    return "".join(f"&#{ord(ch)};" for ch in text)


def _dec_html(text: str) -> str:
    return html.unescape(text)


# --------------------------------------------------------------------------
# registry

CODECS: dict[str, Codec] = {}


def _reg(
    name: str, enc: Encoder, dec: Decoder | None, category: str, desc: str
) -> None:
    CODECS[name] = Codec(name, enc, dec, category, desc)


_reg(
    "spaces",
    _enc_spaces,
    _dec_spaces,
    "visual",
    "Letter-spaced text ('p a y l o a d') — evades substring matching, stays readable",
)
_reg(
    "circle",
    _map_encode(_CIRCLE),
    _map_decode(_CIRCLE),
    "visual",
    "Circled letters (ⓟⓐⓨⓛⓞⓐⓓ)",
)
_reg(
    "fullwidth",
    _map_encode(_FULLWIDTH),
    _map_decode(_FULLWIDTH),
    "visual",
    "Fullwidth latin (ｐａｙｌｏａｄ)",
)
_reg(
    "smallcaps",
    _map_encode(_SMALLCAPS_MAP),
    _map_decode(_SMALLCAPS_MAP),
    "visual",
    "Small caps (ᴘᴀʏʟᴏᴀᴅ)",
)
_reg(
    "math-bold",
    _map_encode(_MATH_BOLD),
    _map_decode(_MATH_BOLD),
    "visual",
    "Mathematical bold (𝐩𝐚𝐲𝐥𝐨𝐚𝐝)",
)
_reg(
    "math-italic",
    _map_encode(_MATH_ITALIC),
    _map_decode(_MATH_ITALIC),
    "visual",
    "Mathematical italic (𝑝𝑎𝑦𝑙𝑜𝑎𝑑)",
)
_reg(
    "math-bold-italic",
    _map_encode(_MATH_BOLD_ITALIC),
    _map_decode(_MATH_BOLD_ITALIC),
    "visual",
    "Mathematical bold italic (𝒑𝒂𝒚𝒍𝒐𝒂𝒅)",
)
_reg(
    "math-script",
    _map_encode(_MATH_SCRIPT),
    _map_decode(_MATH_SCRIPT),
    "visual",
    "Mathematical script (𝓅𝒶𝓎𝓁𝑜𝒶𝒹)",
)
_reg(
    "math-fraktur",
    _map_encode(_MATH_FRAKTUR),
    _map_decode(_MATH_FRAKTUR),
    "visual",
    "Mathematical fraktur (𝔭𝔞𝔶𝔩𝔬𝔞𝔡)",
)
_reg(
    "math-double",
    _map_encode(_MATH_DOUBLE),
    _map_decode(_MATH_DOUBLE),
    "visual",
    "Double-struck (𝕡𝕒𝕪𝕝𝕠𝕒𝕕)",
)
_reg(
    "math-mono",
    _map_encode(_MATH_MONO),
    _map_decode(_MATH_MONO),
    "visual",
    "Monospace mathematical (𝚙𝚊𝚢𝚕𝚘𝚊𝚍)",
)
_reg(
    "regional",
    _map_encode(_REGIONAL),
    None,
    "visual",
    "Regional indicator symbols (🇵 🇦 🇾 ...)",
)
_reg(
    "upside-down",
    _enc_upside_down,
    _dec_upside_down,
    "visual",
    "Flipped characters, string reversed (pɐʎl...",
)
_reg(
    "strikethrough",
    _enc_strikethrough,
    _strip_combining,
    "visual",
    "Combining long stroke overlay (p̶a̶y̶l̶...)",
)
_reg(
    "underline",
    _enc_underline,
    _strip_combining,
    "visual",
    "Combining low line (p̲a̲y̲l̲...)",
)
_reg(
    "braille",
    _map_encode(_BRAILLE),
    _map_decode(_BRAILLE),
    "visual",
    "Braille patterns (⠏⠁⠽⠇...)",
)
_reg(
    "homoglyph",
    _map_encode(_HOMOGLYPH),
    None,
    "visual",
    "Cyrillic homoglyphs — renders identical, compares different",
)
_reg(
    "zwsp",
    _enc_zwsp,
    _dec_zwsp,
    "invisible",
    "Zero-width space between every character",
)
_reg(
    "tag",
    _enc_tag,
    _dec_tag,
    "invisible",
    "Unicode tag characters (invisible in most renderers)",
)
_reg("base64", _enc_base64, _dec_base64, "classic", "Base64")
_reg("hex", _enc_hex, _dec_hex, "classic", "Hexadecimal")
_reg("rot13", _enc_rot13, _enc_rot13, "classic", "ROT13")
_reg("caesar", _enc_caesar, _dec_caesar, "classic", "Caesar shift +3")
_reg("binary", _enc_binary, _dec_binary, "classic", "8-bit binary, space separated")
_reg("url", _enc_url, _dec_url, "classic", "Percent-encoding")
_reg("html", _enc_html, _dec_html, "classic", "Numeric HTML entities")
_reg("morse", _enc_morse, _dec_morse, "classic", "Morse code")
_reg("nato", _enc_nato, _dec_nato, "classic", "NATO phonetic alphabet")
_reg("leet", _map_encode(_LEET), None, "classic", "Leetspeak substitutions")
_reg("reverse", lambda s: s[::-1], lambda s: s[::-1], "classic", "Reverse the string")


def encode(name: str, text: str) -> str:
    return CODECS[name].encode(text)


def decode(name: str, text: str) -> str:
    codec = CODECS[name]
    if codec.decode is None:
        raise ValueError(f"{name} is not losslessly decodable")
    return codec.decode(text)
