"""CLI banner. The last line carries an invisible tag-encoded message —
a self-demo of mysterio's own smuggling codec. Decode it:

    mysterio logo | mysterio encode -d -m tag -
"""

from __future__ import annotations

from . import encoders as E

ART = """
███╗   ███╗██╗   ██╗███████╗████████╗███████╗██████╗ ██╗ ██████╗
████╗ ████║╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝██╔══██╗██║██╔═══██╗
██╔████╔██║ ╚████╔╝ ███████╗   ██║   █████╗  ██████╔╝██║██║   ██║
██║╚██╔╝██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██╔══██╗██║██║   ██║
██║ ╚═╝ ██║   ██║   ███████║   ██║   ███████╗██║  ██║██║╚██████╔╝
╚═╝     ╚═╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝
""".strip("\n")

TAGLINE = "the payload workbench for AI security research"

HIDDEN = "the quiet part out loud"


def banner() -> str:
    return f"{ART}\n{TAGLINE}\n{E.encode('tag', HIDDEN)}"
