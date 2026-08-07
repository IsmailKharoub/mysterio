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


def gen_openapi(lines: int = 80, seed: str = "openapi") -> str:
    """OpenAPI YAML fragments (API-spec surface noise)."""
    rng = random.Random(seed)
    nouns = [
        "contacts",
        "deals",
        "threads",
        "exports",
        "segments",
        "webhooks",
        "owners",
    ]
    out: list[str] = []
    while len(out) < lines:
        noun = rng.choice(nouns)
        rid = _hex_token(seed, len(out), 8)
        out.extend(
            [
                f"  /v3/{noun}/{rid}:",
                "    get:",
                f'      summary: "List {noun} scoped to portal"',
                f"      operationId: list_{noun}_{rid}",
                "      parameters:",
                f"        - {{name: limit, in: query, schema: {{type: integer, default: {rng.choice([50, 100])}}}}}",
                "        - {name: after, in: query, schema: {type: string}}",
                "      responses:",
                f'        "200": {{description: paged {noun}}}',
                '        "429": {description: rate limited, retry-after seconds}',
            ]
        )
    return "\n".join(out[:lines])


def gen_git_diff(lines: int = 80, seed: str = "diff") -> str:
    """Unified-diff hunks (code-review surface noise)."""
    rng = random.Random(seed)
    files = [
        "src/handlers/sync.py",
        "src/lib/stream.ts",
        "internal/queue/worker.go",
        "pkg/exporter/chunk.py",
        "web/components/Thread.tsx",
    ]
    out: list[str] = []
    i = 0
    while len(out) < lines:
        f = rng.choice(files)
        out.append(f"diff --git a/{f} b/{f}")
        out.append(
            f"index {_hex_token(seed, i, 7)}..{_hex_token(seed, i + 1, 7)} 100644"
        )
        out.append(f"--- a/{f}")
        out.append(f"+++ b/{f}")
        out.append(
            f"@@ -{rng.randint(10, 800)},{rng.randint(4, 12)} +{rng.randint(10, 800)},{rng.randint(4, 12)} @@"
        )
        for j in range(rng.randint(4, 8)):
            sign = rng.choice([" ", " ", "-", "+"])
            out.append(
                f"{sign}    {_token(seed, i * 10 + j, 12)} = process(chunk, flags)"
            )
        i += 1
    return "\n".join(out[:lines])


def gen_csv(lines: int = 60, seed: str = "csv") -> str:
    """Tabular export rows (data-surface noise)."""
    rng = random.Random(seed)
    out = ["id,contact_email,deal_value,stage,updated_at"]
    stages = ["discovery", "demo", "negotiation", "closed-won", "closed-lost"]
    for i in range(lines):
        out.append(
            f"{10000 + i},user{_hex_token(seed, i, 6)}@example.com,"
            f"{rng.randint(4, 900) * 1000},{rng.choice(stages)},2026-05-{rng.randint(1, 28):02d}"
        )
    return "\n".join(out)


def gen_min_js(lines: int = 30, seed: str = "minjs") -> str:
    """Minified-JS bundle lines (web-bundle surface noise)."""
    out = []
    for i in range(lines):
        body = _token(seed, i, 48)
        out.append(
            f'!function(e,t){{"object"==typeof exports&&"undefined"!=typeof module?'
            f't(exports):e["{_hex_token(seed, i, 6)}"]={body[:20]}}}();/* chunk {i} */'
        )
    return "\n".join(out)


def gen_sql(lines: int = 60, seed: str = "sql") -> str:
    """INSERT statement rows (DB-seed surface noise)."""
    rng = random.Random(seed)
    out = []
    for i in range(lines):
        out.append(
            f"INSERT INTO events (id, actor, verb, object_id, created_at) VALUES "
            f"('{_hex_token(seed, i, 12)}', 'system', 'synced', {rng.randint(1000, 99999)}, "
            f"'2026-05-04 10:{i % 60:02d}:00Z');"
        )
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
    "openapi": JunkStyle("openapi", gen_openapi, "OpenAPI YAML spec fragments"),
    "git-diff": JunkStyle("git-diff", gen_git_diff, "Unified diff hunks"),
    "csv": JunkStyle("csv", gen_csv, "Tabular export rows (with header)"),
    "min-js": JunkStyle("min-js", gen_min_js, "Minified JS bundle lines"),
    "sql": JunkStyle("sql", gen_sql, "SQL INSERT seed rows"),
}


def generate(style: str, **kwargs: object) -> str:
    return STYLES[style].generate(**kwargs)


def lines_for_tokens(style: str, approx_tokens: int, seed: str = "cal") -> int:
    """Resolve a token budget to a line/row count by self-calibration:
    generate a probe, estimate tokens as chars/4, scale to the target."""
    if style == "base64":
        probe = gen_base64_blob(size=320, seed=seed)
        per_unit = len(probe) / 4 / 10  # 320 bytes ~ 10 wrapped rows
        return max(1, round(approx_tokens / per_unit))
    probe = STYLES[style].generate(lines=10, seed=seed)
    per_line = len(probe) / 4 / 10
    return max(1, round(approx_tokens / per_line))
