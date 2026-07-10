#!/usr/bin/env python3
"""Translate SRT subtitle files from one language to another (default: English -> French)."""

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_BLOCK_SEP = "\n\n"


@dataclass
class SubtitleBlock:
    index: str
    timestamp: str
    text: str


def parse_srt(content: str) -> list[SubtitleBlock]:
    """Parse raw .srt content into a list of SubtitleBlock entries."""
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    for raw_block in content.strip().split(_BLOCK_SEP):
        lines = raw_block.strip("\n").split("\n")
        if len(lines) < 2:
            continue
        index, timestamp, *text_lines = lines
        if "-->" not in timestamp:
            continue
        blocks.append(SubtitleBlock(index.strip(), timestamp.strip(), "\n".join(text_lines)))
    return blocks


def render_srt(blocks: list[SubtitleBlock]) -> str:
    """Render a list of SubtitleBlock entries back into .srt format."""
    return _BLOCK_SEP.join(f"{b.index}\n{b.timestamp}\n{b.text}" for b in blocks) + "\n"


class Translator:
    """Base interface for translation backends."""

    def translate(self, text: str, source: str, target: str) -> str:
        raise NotImplementedError


class GoogleTranslateBackend(Translator):
    """Translation backend backed by the free Google Translate endpoint via deep-translator."""

    def __init__(self):
        from deep_translator import GoogleTranslator

        self._GoogleTranslator = GoogleTranslator

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text
        return self._GoogleTranslator(source=source, target=target).translate(text)


def translate_blocks(
    blocks: list[SubtitleBlock],
    translator: Translator,
    source: str = "en",
    target: str = "fr",
    delay: float = 0.0,
    on_progress=None,
) -> list[SubtitleBlock]:
    """Translate the text of each subtitle block, keeping index/timestamp untouched."""
    translated = []
    for i, block in enumerate(blocks, start=1):
        translated_text = translator.translate(block.text, source, target)
        translated.append(SubtitleBlock(block.index, block.timestamp, translated_text))
        if on_progress:
            on_progress(i, len(blocks))
        if delay and i < len(blocks):
            time.sleep(delay)
    return translated


def translate_srt_file(
    input_path: Path,
    output_path: Path,
    translator: Translator,
    source: str = "en",
    target: str = "fr",
    delay: float = 0.0,
    on_progress=None,
) -> int:
    """Translate an .srt file end-to-end. Returns the number of blocks translated."""
    content = input_path.read_text(encoding="utf-8")
    blocks = parse_srt(content)
    if not blocks:
        raise ValueError(f"No subtitle blocks found in {input_path} - is this a valid .srt file?")

    translated_blocks = translate_blocks(blocks, translator, source, target, delay, on_progress)
    output_path.write_text(render_srt(translated_blocks), encoding="utf-8")
    return len(blocks)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Translate SRT subtitle files (default: English -> French)")
    parser.add_argument("input", type=Path, help="Path to the input .srt file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Path to the output .srt file (default: <input-stem>.<target>.srt)",
    )
    parser.add_argument("--source", default="en", help="Source language code (default: en)")
    parser.add_argument("--target", default="fr", help="Target language code (default: fr)")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay in seconds between translation requests, to avoid rate limits (default: 0.2)",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")

    output = args.output or args.input.with_suffix(f".{args.target}.srt")

    try:
        translator = GoogleTranslateBackend()
    except ImportError:
        parser.error(
            "The 'deep-translator' package is required. Install it with: pip install -r requirements.txt"
        )

    def report(done: int, total: int) -> None:
        print(f"\rTranslating... {done}/{total}", end="", file=sys.stderr, flush=True)

    try:
        count = translate_srt_file(
            args.input, output, translator, args.source, args.target, args.delay, on_progress=report
        )
    except ValueError as exc:
        parser.error(str(exc))
    except Exception as exc:  # translation backend / network failures
        print(f"\nTranslation failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nTranslated {count} subtitle blocks: {args.input} -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
