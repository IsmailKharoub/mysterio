"""Context-noise ("junk") generators.

Junk is inert-looking serialized/technical content placed around a payload to
camouflage it inside a host message or tool result. Each generator produces
deterministic-shaped output (seedable) in a style that plausibly occurs in a
real surface: framework streams, API logs, hexdumps, stack traces, etc.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import string
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class JunkStyle:
    name: str
    generate: Callable[..., str]
    description: str


def _token(seed: str, i: int, n: int = 24) -> str:
    digest = hashlib.sha256(f"{seed}-{i}".encode()).digest()
    return base64.b64encode(digest)[:n].decode()


def _hex_token(seed: str, i: int, n: int = 16) -> str:
    return hashlib.sha256(f"{seed}-{i}".encode()).hexdigest()[:n]


# --------------------------------------------------------------------------
# generators


def gen_rsc(lines: int = 140, start: int = 40, seed: str = "rsc-chunk") -> str:
    """React Server Components serialized stream chunks."""
    out = []
    for i in range(lines):
        tok = _token(seed, i)
        flags = ["prefetch", "idle"] if i % 3 else ["prefetch"]
        out.append(
            f'{start + i}:{{"stream":"rsc","chunk":"{tok}","flags":{json.dumps(flags)}}}'
        )
    return "\n".join(out)


def gen_next_f(lines: int = 40, seed: str = "next-f") -> str:
    """Next.js self.__next_f.push payload rows."""
    out = []
    for i in range(lines):
        tok = _token(seed, i, 24)
        out.append(
            f'])self.__next_f.push([1,"{i:x}:[\\"$\\",\\"$L{10 + i}\\",null,\\"{tok}\\"]"])'
        )
    return "\n".join(out)


def gen_http_log(lines: int = 140, seed: str = "http", status_every: int = 7) -> str:
    """HTTP access/debug log lines (plausible API debug capture)."""
    rng = random.Random(seed)
    paths = [
        "/api/v3/objects",
        "/conversations/v1/threads",
        "/api/v2/messages",
        "/graphql",
        "/auth/token/refresh",
        "/exporter/v1/chunks",
        "/healthz",
    ]
    methods = ["GET", "POST", "PUT", "PATCH"]
    out = []
    base_ts = 1780000000
    for i in range(lines):
        ts = base_ts + i * rng.randint(1, 9)
        status = (
            rng.choice([200, 200, 200, 201, 204, 304])
            if i % status_every
            else rng.choice([429, 500, 503])
        )
        ms = rng.randint(3, 480)
        rid = _hex_token(seed, i, 12)
        out.append(
            f"[2026-05-04T10:{40 + (i // 60) % 20:02d}:{i % 60:02d}Z] {rng.choice(methods)} "
            f"{rng.choice(paths)} {status} {ms}ms req={rid} bytes={rng.randint(200, 48000)}"
        )
    return "\n".join(out)


def gen_hexdump(lines: int = 60, seed: str = "hex") -> str:
    """Classic hexdump rows: offset, 16 bytes, ascii gutter."""
    out = []
    for i in range(lines):
        data = hashlib.sha256(f"{seed}-{i}".encode()).digest()[:16]
        hexpart = " ".join(f"{b:02x}" for b in data)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        out.append(f"{i * 16:08x}  {hexpart:<47}  |{ascii_part}|")
    return "\n".join(out)


def gen_stacktrace(frames: int = 24, seed: str = "trace") -> str:
    """Minified-js-looking stack trace frames."""
    rng = random.Random(seed)
    fns = [
        "onChunk",
        "flushSync",
        "processQueue",
        "t.default",
        "e.exports",
        "hydrateRoot",
        "scheduleCallback",
        "performWork",
        "resolveRetry",
    ]
    out = []
    for i in range(frames):
        fn = rng.choice(fns)
        out.append(
            f"    at {fn} (https://cdn.assets.local/_next/static/chunks/"
            f"{_hex_token(seed, i, 16)}.js:{rng.randint(1, 90)}:{rng.randint(1000, 99000)})"
        )
    return "\n".join(out)


def gen_syslog(lines: int = 80, seed: str = "syslog") -> str:
    rng = random.Random(seed)
    units = [
        "sshd",
        "cron",
        "systemd",
        "networkd-dispatcher",
        "exporterd",
        "node_exporter",
    ]
    out = []
    for i in range(lines):
        unit = rng.choice(units)
        pid = rng.randint(400, 32000)
        out.append(
            f"May  4 10:{i % 60:02d}:{rng.randint(10, 59)} prod-edge-02 {unit}[{pid}]: "
            f"connection reset by peer (fd={rng.randint(3, 40)}, seq={_hex_token(seed, i, 8)})"
        )
    return "\n".join(out)


def gen_base64_blob(size: int = 4096, seed: str = "blob") -> str:
    """MIME-wrapped base64 blob (attachment-shaped)."""
    raw = hashlib.shake_256(seed.encode()).digest(size)
    b64 = base64.b64encode(raw).decode()
    return "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))


def gen_jsonl(lines: int = 60, seed: str = "jsonl") -> str:
    """Telemetry-shaped JSONL rows."""
    rng = random.Random(seed)
    out = []
    for i in range(lines):
        row = {
            "ts": f"2026-05-04T10:{i % 60:02d}:{rng.randint(10, 59):02d}Z",
            "lvl": rng.choice(["info", "info", "debug", "warn"]),
            "msg": rng.choice(
                [
                    "chunk flushed",
                    "retry scheduled",
                    "prefetch resolved",
                    "buffer compacted",
                    "stream reassembled",
                ]
            ),
            "trace": _hex_token(seed, i, 16),
            "span": "".join(rng.choice(string.digits) for _ in range(8)),
        }
        out.append(json.dumps(row))
    return "\n".join(out)


STYLES: dict[str, JunkStyle] = {
    "rsc": JunkStyle(
        "rsc", gen_rsc, "React Server Components stream chunks (N:{...} rows)"
    ),
    "next_f": JunkStyle("next_f", gen_next_f, "Next.js __next_f.push payload rows"),
    "http-log": JunkStyle("http-log", gen_http_log, "HTTP access/debug log lines"),
    "hexdump": JunkStyle("hexdump", gen_hexdump, "Hex dump rows with ascii gutter"),
    "stacktrace": JunkStyle("stacktrace", gen_stacktrace, "Minified JS stack frames"),
    "syslog": JunkStyle("syslog", gen_syslog, "Linux syslog lines"),
    "base64": JunkStyle("base64", gen_base64_blob, "MIME-wrapped base64 blob"),
    "jsonl": JunkStyle("jsonl", gen_jsonl, "Telemetry JSONL rows"),
}


def generate(style: str, **kwargs: object) -> str:
    return STYLES[style].generate(**kwargs)
