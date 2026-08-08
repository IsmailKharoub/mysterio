import pytest

textual = pytest.importorskip("textual")

from textual.widgets import DataTable, RichLog, TextArea  # noqa: E402

from mysterio.lab import MysterioLab  # noqa: E402


@pytest.mark.asyncio
async def test_lab_boots_with_tabs():
    app = MysterioLab()
    async with app.run_test():
        assert app.query_one("#tab-builder")
        assert app.query_one("#tab-encoders")
        assert app.query_one("#tab-junk")
        assert app.query_one("#tab-library")


@pytest.mark.asyncio
async def test_builder_renders_default_recipe():
    app = MysterioLab()
    async with app.run_test() as pilot:
        await pilot.pause()
        render = app.query_one("#render", RichLog)
        text = "\n".join(line.text for line in render.lines)
        assert '"stream":"rsc"' in text
        assert "[/function_results]" in text


@pytest.mark.asyncio
async def test_builder_yaml_error_surfaces():
    app = MysterioLab()
    async with app.run_test() as pilot:
        editor = app.query_one("#recipe-editor", TextArea)
        editor.text = "blocks: [unclosed"
        await pilot.pause()
        render = app.query_one("#render", RichLog)
        text = "\n".join(line.text for line in render.lines)
        assert "YAML error" in text


@pytest.mark.asyncio
async def test_encoder_table_populates():
    app = MysterioLab()
    async with app.run_test() as pilot:
        await pilot.click("#tab-encoders")
        table = app.query_one("#encode-table", DataTable)
        assert table.row_count == 0
        inp = app.query_one("#encode-input")
        inp.value = "hello"
        await pilot.pause()
        assert table.row_count > 25


@pytest.mark.asyncio
async def test_junk_controls_row_layout():
    """The style Select must be readable and the tokens input on-screen."""
    app = MysterioLab()
    async with app.run_test() as pilot:
        await pilot.click("#tab-junk")
        await pilot.pause()
        screen_w = app.screen.size.width
        style = app.query_one("#junk-style")
        tokens = app.query_one("#junk-tokens")
        assert style.region.width >= 20
        assert tokens.region.x >= 0
        assert tokens.region.x + tokens.region.width <= screen_w


@pytest.mark.asyncio
async def test_junk_dose_clamped_and_noted():
    app = MysterioLab()
    async with app.run_test() as pilot:
        await pilot.click("#tab-junk")
        lines = app.query_one("#junk-lines")
        lines.value = "100000"
        await pilot.pause()
        stats = str(app.query_one("#junk-stats").render())
        assert "clamped to 5,000" in stats

        tokens = app.query_one("#junk-tokens")
        tokens.value = "500"
        await pilot.pause()
        stats = str(app.query_one("#junk-stats").render())
        assert "overrides lines" in stats
