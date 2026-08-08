from typer.testing import CliRunner

from mysterio import encoders as E
from mysterio import logo as LG
from mysterio.cli import app

runner = CliRunner()


def test_logo_prints_art():
    result = runner.invoke(app, ["logo"])
    assert result.exit_code == 0
    assert "███" in result.output
    assert LG.TAGLINE in result.output


def test_banner_hides_decodable_message():
    """The banner smuggles an invisible line, decodable with mysterio itself."""
    decoded = E.decode("tag", LG.banner())
    assert LG.HIDDEN in decoded


def test_hidden_message_roundtrips_invisibly():
    encoded = E.encode("tag", LG.HIDDEN)
    assert LG.HIDDEN not in encoded  # invisible on the wire
    assert E.decode("tag", encoded) == LG.HIDDEN
