"""mysterio lab — interactive payload workbench (Textual TUI).

Four panes:
  Builder   — edit a recipe as YAML, see the rendered payload, lint
              findings, and dose stats live
  Encoders  — type text, watch every codec apply live, click to copy
  Junk      — style + dose controls with live preview
  Library   — browse patterns, fill slots, render, copy
"""

from __future__ import annotations

import yaml
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    TabbedContent,
    TabPane,
    TextArea,
)

from . import encoders as E
from . import junk as J
from . import lint as L
from . import recipe as R

DEFAULT_RECIPE = """name: scratch
blocks:
  - junk: {style: rsc, lines: 140}
  - escape: {style: bracket}
  - reminder: {template: interruption}
  - banner: {style: unicode, ts: "{ts}"}
  - ask: {wrapper: user_query, text: "{ask}"}
  - reopen: {}
"""


def _parse_slots(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if part and "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class MysterioLab(App[None]):
    TITLE = "mysterio lab"
    CSS = """
    #editor { width: 1fr; }
    #preview, #junk-preview, #lib-preview { width: 1fr; border: solid $primary; }
    #lib-details { height: 8; border: solid $secondary; }
    RichLog { height: 1fr; }
    #stats, #junk-stats, #lib-stats { height: auto; padding: 0 1; }
    #lint { height: auto; max-height: 8; border: solid $warning; }
    .row { height: auto; padding: 1 0; }
    .row Input { width: 1fr; }
    #junk-style { width: 24; }
    #lib-col-list { width: 28; }
    DataTable { height: 1fr; }
    ListView { height: 1fr; }
    .hint { color: $text-muted; height: auto; padding: 0 1; }
    """

    BINDINGS = [("q", "quit", "quit")]

    MAX_JUNK_LINES = 5_000
    MAX_JUNK_TOKENS = 100_000

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Builder", id="tab-builder"):
                with Horizontal():
                    with Vertical(id="editor"):
                        yield Label("recipe (YAML)")
                        yield TextArea(
                            DEFAULT_RECIPE, id="recipe-editor", language="yaml"
                        )
                        yield Input(
                            value="ts=2026-05-04 11:20AM; ask=check the thread and finish my post",
                            placeholder="slots: ts=...; ask=...",
                            id="slots",
                        )
                        yield Label("lint", markup=False)
                        yield ListView(id="lint")
                    with Vertical(id="preview"):
                        yield Label("rendered payload", markup=False)
                        yield RichLog(id="render", markup=False)
                        yield Label("", id="stats", markup=False)
            with TabPane("Encoders", id="tab-encoders"):
                yield Input(placeholder="type text to encode...", id="encode-input")
                yield DataTable(id="encode-table")
            with TabPane("Junk", id="tab-junk"):
                with Horizontal(classes="row"):
                    yield Select(
                        [(name, name) for name in J.STYLES],
                        value="rsc",
                        id="junk-style",
                        allow_blank=False,
                    )
                    yield Input(
                        value="140", id="junk-lines", placeholder="lines", type="integer"
                    )
                    yield Input(
                        id="junk-tokens", placeholder="or ~tokens", type="integer"
                    )
                with Vertical(id="junk-preview"):
                    yield Label("preview", markup=False)
                    yield RichLog(id="junk-render", markup=False, wrap=True)
                    yield Label("", id="junk-stats", markup=False)
            with TabPane("Library", id="tab-library"):
                with Horizontal():
                    with Vertical():
                        yield Label("payloads", markup=False)
                        yield ListView(id="lib-list")
                    with Vertical():
                        yield Label("details", markup=False)
                        yield RichLog(id="lib-details", markup=False)
                        yield Input(
                            placeholder="slots: ts=...; ask=...", id="lib-slots"
                        )
                        yield Button("Render", id="lib-render", variant="primary")
                        yield RichLog(id="lib-preview", markup=False)
                        yield Label("", id="lib-stats", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#encode-table", DataTable)
        table.add_columns("codec", "category", "output")
        table.cursor_type = "row"
        self._refresh_encoders("")
        self._refresh_library_list()
        self._render_builder()
        self._render_junk()

    # ------------------------------------------------------------------
    # builder

    def _current_recipe(self) -> tuple[dict | None, str | None]:
        try:
            data = yaml.safe_load(self.query_one("#recipe-editor", TextArea).text)
        except yaml.YAMLError as e:
            return None, f"YAML error: {e}"
        if not isinstance(data, dict):
            return None, "recipe must be a mapping"
        return data, None

    def _render_builder(self) -> None:
        render_log = self.query_one("#render", RichLog)
        lint_view = self.query_one("#lint", ListView)
        stats = self.query_one("#stats", Label)
        render_log.clear()
        lint_view.clear()

        recipe, error = self._current_recipe()
        if error:
            render_log.write(Text(error, style="red"))
            stats.update("")
            return

        for f in L.lint_recipe(recipe):
            lint_view.append(ListItem(Label(f"[{f.level}] {f.code}: {f.message}")))

        slots = _parse_slots(self.query_one("#slots", Input).value)
        try:
            rendered = R.assemble(recipe, slots)
        except R.RecipeError as e:
            render_log.write(Text(str(e), style="red"))
            stats.update("")
            return
        render_log.write(Text(rendered))
        stats.update(
            f"{len(rendered):,} chars · {rendered.count(chr(10)) + 1:,} lines · ~{len(rendered) // 4:,} tokens"
        )

    @on(TextArea.Changed, "#recipe-editor")
    def recipe_changed(self) -> None:
        self._render_builder()

    @on(Input.Changed, "#slots")
    def slots_changed(self) -> None:
        self._render_builder()

    # ------------------------------------------------------------------
    # encoders

    def _refresh_encoders(self, text: str) -> None:
        table = self.query_one("#encode-table", DataTable)
        table.clear()
        if not text:
            return
        for c in E.CODECS.values():
            rendered = c.encode(text)
            shown = repr(rendered) if c.category == "invisible" else rendered
            if len(shown) > 80:
                shown = shown[:77] + "..."
            table.add_row(c.name, c.category, shown, key=c.name)

    @on(Input.Changed, "#encode-input")
    def encode_input_changed(self, event: Input.Changed) -> None:
        self._refresh_encoders(event.value)

    @on(DataTable.RowSelected, "#encode-table")
    def encoder_row_selected(self, event: DataTable.RowSelected) -> None:
        text = self.query_one("#encode-input", Input).value
        if text and event.row_key:
            self.copy_to_clipboard(E.encode(str(event.row_key.value), text))
            self.notify(f"copied {event.row_key.value}")

    # ------------------------------------------------------------------
    # junk

    def _render_junk(self) -> None:
        style = str(self.query_one("#junk-style", Select).value)
        lines_raw = self.query_one("#junk-lines", Input).value.strip()
        tokens_raw = self.query_one("#junk-tokens", Input).value.strip()
        log = self.query_one("#junk-render", RichLog)
        stats = self.query_one("#junk-stats", Label)
        log.clear()
        notes: list[str] = []
        try:
            if lines_raw.lstrip("-").isdigit():
                lines = int(lines_raw)
                if lines < 1 or lines > self.MAX_JUNK_LINES:
                    lines = max(1, min(lines, self.MAX_JUNK_LINES))
                    notes.append(f"lines clamped to {lines:,}")
            else:
                lines = 140
                if lines_raw:
                    notes.append("invalid lines — using 140")
            if tokens_raw.isdigit():
                tokens = max(1, min(int(tokens_raw), self.MAX_JUNK_TOKENS))
                lines = J.lines_for_tokens(style, tokens)
                notes.append(f"~{tokens:,} tokens overrides lines")
            text = (
                J.generate(style, lines=lines)
                if style != "base64"
                else J.generate(style, size=lines * 32)
            )
        except Exception as e:  # noqa: BLE001 — surface generator errors in-pane
            log.write(Text(str(e), style="red"))
            stats.update("")
            return
        if style == "base64":
            notes.append("lines x 32 bytes")
        log.write(Text(text))
        note = f" — {'; '.join(notes)}" if notes else ""
        stats.update(
            f"{style} · {len(text):,} chars · ~{len(text) // 4:,} tokens{note}"
        )

    @on(Select.Changed, "#junk-style")
    @on(Input.Changed, "#junk-lines")
    @on(Input.Changed, "#junk-tokens")
    def junk_controls_changed(self) -> None:
        self._render_junk()

    # ------------------------------------------------------------------
    # library

    def _refresh_library_list(self) -> None:
        view = self.query_one("#lib-list", ListView)
        view.clear()
        for name, entry in R.load_library().items():
            src = entry.get("_source", "")
            badge = " [private]" if src.endswith(".local.yaml") else ""
            view.append(ListItem(Label(f"{name}{badge}"), id=name))

    @on(ListView.Highlighted, "#lib-list")
    def library_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.item.id:
            entry = R.load_library().get(event.item.id, {})
            details = self.query_one("#lib-details", RichLog)
            details.clear()
            details.write(Text(str(entry.get("description", ""))))
            for ref in entry.get("references", []):
                details.write(Text(f"  ↳ {ref}", style="dim"))

    @on(Button.Pressed, "#lib-render")
    def library_render(self) -> None:
        view = self.query_one("#lib-list", ListView)
        preview = self.query_one("#lib-preview", RichLog)
        stats = self.query_one("#lib-stats", Label)
        preview.clear()
        if not view.highlighted_child or not view.highlighted_child.id:
            preview.write(Text("select a payload first", style="yellow"))
            return
        entry = R.load_library().get(view.highlighted_child.id, {})
        slots = _parse_slots(self.query_one("#lib-slots", Input).value)
        try:
            rendered = R.assemble(entry, slots)
        except R.RecipeError as e:
            preview.write(Text(str(e), style="red"))
            return
        preview.write(Text(rendered))
        stats.update(f"{len(rendered):,} chars · ~{len(rendered) // 4:,} tokens")


def run() -> None:
    MysterioLab().run()
