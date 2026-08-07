import pytest

textual = pytest.importorskip("textual")

from textual.widgets import DataTable, RichLog, TextArea

from mysterio.lab import MysterioLab


@pytest.mark.asyncio
async def test_lab_boots_with_tabs():
    app = MysterioLab()
    async with app.run_test() as pilot:
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
