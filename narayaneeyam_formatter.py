#!/usr/bin/env python3
"""Narayaneeyam formatter.

Reads one or more UTF-8 Sanskrit sloka text files and produces Tamil study text
in the required study layout using the OpenAI Responses API.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

from openai import OpenAI

LOGGER = logging.getLogger("narayaneeyam_formatter")


# ---------------------------- Data Models -----------------------------------

@dataclass
class SlokaResult:
    """Structured result for one sloka."""

    slokam_tamil_script: str
    split_lines: List[str]
    meaning: str


# ---------------------------- Prompting -------------------------------------

SYSTEM_INSTRUCTIONS = """
You are a careful assistant that converts Sanskrit Narayaneeyam slokas into a
Tamil study format.

Output ONLY strict JSON with this schema:
{
  "slokam_tamil_script": "string",
  "split_lines": ["string", "..."],
  "meaning": "string"
}

Rules:
- slokam_tamil_script must be fully in Tamil script.
- split_lines must be simple, student-friendly Tamil phrase splits.
- meaning must be a short, clear Tamil prose meaning.
- No markdown, no extra keys, no comments.
""".strip()


def build_user_prompt(sloka_text: str, title: str | None = None) -> str:
    """Builds the user prompt for one sloka conversion."""
    title_part = f"Context title: {title}\n" if title else ""
    return (
        f"{title_part}Convert this Sanskrit sloka to Tamil study format fields.\n\n"
        f"SLOKA:\n{sloka_text.strip()}\n"
    )


# ---------------------------- Parsing Helpers -------------------------------


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract JSON from model text safely.

    Supports:
    - direct JSON object
    - JSON in code blocks
    - mixed text where first {...} object appears
    """
    text = text.strip()

    # 1) direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) fenced code block
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3) first balanced-ish object from first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj

    raise ValueError("Could not parse valid JSON object from model output.")


def normalize_result(raw: dict[str, Any]) -> SlokaResult:
    """Validate and normalize a model JSON payload."""
    slokam = str(raw.get("slokam_tamil_script", "")).strip()
    split_lines_raw = raw.get("split_lines", [])
    meaning = str(raw.get("meaning", "")).strip()

    if not isinstance(split_lines_raw, list):
        split_lines_raw = [str(split_lines_raw)] if split_lines_raw else []

    split_lines = [str(item).strip() for item in split_lines_raw if str(item).strip()]

    if not slokam:
        raise ValueError("Missing slokam_tamil_script in response JSON.")
    if not split_lines:
        raise ValueError("Missing split_lines in response JSON.")
    if not meaning:
        raise ValueError("Missing meaning in response JSON.")

    return SlokaResult(slokam_tamil_script=slokam, split_lines=split_lines, meaning=meaning)


# ---------------------------- Core Logic ------------------------------------


def split_sloka_blocks(text: str) -> List[str]:
    """Split input by blank lines into sloka blocks."""
    blocks = re.split(r"\n\s*\n", text.strip())
    return [block.strip() for block in blocks if block.strip()]


def read_slokas_from_files(paths: Iterable[Path]) -> List[str]:
    """Read sloka blocks from one or more input files."""
    all_blocks: List[str] = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        blocks = split_sloka_blocks(content)
        LOGGER.info("Read %d sloka block(s) from %s", len(blocks), path)
        all_blocks.extend(blocks)
    return all_blocks


def render_tamil_output(results: List[SlokaResult], title: str | None = None) -> str:
    """Render final output text in the exact requested layout."""
    pieces: List[str] = []

    if title:
        pieces.append(title)
        pieces.append("")

    for index, result in enumerate(results, start=1):
        pieces.extend(
            [
                f"🔹 ஸ்லோகம் {index}",
                "📖 ஸ்லோகம் (தமிழ் எழுத்து)",
                "",
                result.slokam_tamil_script,
                "",
                "✨ பதவுரை (Split)",
                "",
                *result.split_lines,
                "",
                "🌼 பொருள்",
                "",
                result.meaning,
                "",
            ]
        )

    return "\n".join(pieces).rstrip() + "\n"


def convert_sloka_with_model(client: OpenAI, model: str, sloka: str, title: str | None = None) -> SlokaResult:
    """Call Responses API and robustly parse JSON with fallback."""
    prompt = build_user_prompt(sloka_text=sloka, title=title)

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    # Primary path: SDK convenience text
    text_output = getattr(response, "output_text", "") or ""

    # Fallback path: traverse response output content
    if not text_output:
        try:
            chunks: List[str] = []
            for item in response.output:
                for content in getattr(item, "content", []):
                    text = getattr(content, "text", None)
                    if text:
                        chunks.append(text)
            text_output = "\n".join(chunks).strip()
        except Exception as exc:  # defensive fallback
            raise RuntimeError(f"Could not read model response content: {exc}") from exc

    raw_json = extract_json_from_text(text_output)
    return normalize_result(raw_json)


def chunked(seq: List[str], size: int) -> Iterable[List[str]]:
    """Yield list chunks."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def process(
    input_files: List[Path],
    output_file: Path,
    model: str,
    title: str | None,
    chunk_size: int,
) -> None:
    """Main processing pipeline."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    slokas = read_slokas_from_files(input_files)
    if not slokas:
        raise ValueError("No sloka blocks found in input files.")

    client = OpenAI(api_key=api_key)
    results: List[SlokaResult] = []

    for group in chunked(slokas, chunk_size):
        for sloka in group:
            try:
                result = convert_sloka_with_model(client=client, model=model, sloka=sloka, title=title)
                results.append(result)
            except Exception as exc:
                LOGGER.error("Failed to process sloka block. Reason: %s", exc)
                # Fallback output entry for traceability
                results.append(
                    SlokaResult(
                        slokam_tamil_script="[பிழை: ஸ்லோகம் மாற்றம் தோல்வி]",
                        split_lines=["[பிழை: பதவுரை உருவாக்க முடியவில்லை]"],
                        meaning="[பிழை: பொருள் உருவாக்க முடியவில்லை]",
                    )
                )

    output_text = render_tamil_output(results, title=title)
    output_file.write_text(output_text, encoding="utf-8")
    LOGGER.info("Wrote %d sloka(s) to %s", len(results), output_file)


# ---------------------------- CLI -------------------------------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert Narayaneeyam slokas into Tamil study text format."
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        required=True,
        help="Input UTF-8 text file(s). Each sloka block should be separated by a blank line.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output plain text file path.",
    )
    parser.add_argument(
        "-t",
        "--title",
        default="நாராயணீயம் தசகம் 1",
        help="Optional title to print at the top of output.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model name for Responses API.",
    )
    parser.add_argument(
        "-c",
        "--chunk-size",
        type=int,
        default=3,
        help="Number of sloka blocks to process per chunk loop.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv if argv is not None else sys.argv[1:])

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    input_files = [Path(p) for p in args.input]
    output_file = Path(args.output)

    if args.chunk_size <= 0:
        LOGGER.error("--chunk-size must be a positive integer.")
        return 2

    missing = [str(p) for p in input_files if not p.exists()]
    if missing:
        LOGGER.error("Missing input file(s): %s", ", ".join(missing))
        return 2

    try:
        process(
            input_files=input_files,
            output_file=output_file,
            model=args.model,
            title=args.title,
            chunk_size=args.chunk_size,
        )
        return 0
    except Exception as exc:
        LOGGER.error("Processing failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
