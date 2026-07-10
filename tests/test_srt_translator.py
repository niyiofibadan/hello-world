import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from srt_translator import (  # noqa: E402
    SubtitleBlock,
    Translator,
    parse_srt,
    render_srt,
    translate_blocks,
    translate_srt_file,
)

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:03,500
Hello, welcome to the show.

2
00:00:04,000 --> 00:00:06,200
Today we are talking
about the news.

3
00:00:07,000 --> 00:00:09,800
Thank you for watching, see you next time.
"""


class FakeTranslator(Translator):
    """Deterministic stand-in for a real translation backend, used in tests."""

    PHRASES = {
        "Hello, welcome to the show.": "Bonjour, bienvenue dans l'émission.",
        "Today we are talking\nabout the news.": "Aujourd'hui, nous parlons\ndes informations.",
        "Thank you for watching, see you next time.": "Merci de nous avoir regardés, à la prochaine.",
    }

    def translate(self, text: str, source: str, target: str) -> str:
        return self.PHRASES.get(text, text)


def test_parse_srt_extracts_all_blocks():
    blocks = parse_srt(SAMPLE_SRT)
    assert len(blocks) == 3
    assert blocks[0] == SubtitleBlock("1", "00:00:01,000 --> 00:00:03,500", "Hello, welcome to the show.")
    assert blocks[1].text == "Today we are talking\nabout the news."


def test_parse_srt_handles_crlf_and_bom():
    crlf_content = "\ufeff" + SAMPLE_SRT.replace("\n", "\r\n")
    blocks = parse_srt(crlf_content)
    assert len(blocks) == 3
    assert blocks[0].text == "Hello, welcome to the show."


def test_render_srt_round_trips():
    blocks = parse_srt(SAMPLE_SRT)
    rendered = render_srt(blocks)
    assert parse_srt(rendered) == blocks


def test_translate_blocks_preserves_index_and_timestamp():
    blocks = parse_srt(SAMPLE_SRT)
    translated = translate_blocks(blocks, FakeTranslator(), source="en", target="fr")

    assert [b.index for b in translated] == ["1", "2", "3"]
    assert [b.timestamp for b in translated] == [b.timestamp for b in blocks]
    assert translated[0].text == "Bonjour, bienvenue dans l'émission."
    assert translated[2].text == "Merci de nous avoir regardés, à la prochaine."


def test_translate_srt_file_end_to_end(tmp_path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.fr.srt"
    input_path.write_text(SAMPLE_SRT, encoding="utf-8")

    count = translate_srt_file(input_path, output_path, FakeTranslator(), source="en", target="fr")

    assert count == 3
    output_content = output_path.read_text(encoding="utf-8")
    assert "Bonjour, bienvenue dans l'émission." in output_content
    assert "00:00:01,000 --> 00:00:03,500" in output_content


def test_translate_srt_file_raises_on_no_blocks(tmp_path):
    input_path = tmp_path / "empty.srt"
    output_path = tmp_path / "output.srt"
    input_path.write_text("not a valid srt file", encoding="utf-8")

    try:
        translate_srt_file(input_path, output_path, FakeTranslator())
        assert False, "expected ValueError"
    except ValueError:
        pass
