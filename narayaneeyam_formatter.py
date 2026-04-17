#!/usr/bin/env python3
"""Narayaneeyam formatter.

Converts Sanskrit sloka blocks (from UTF-8 text files and/or PDFs) into
Tamil study text layout using the OpenAI Responses API.
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
from typing import Any, Iterable, List, Sequence

LOGGER = logging.getLogger("narayaneeyam_formatter")


# ---------------------------- Data models ------------------------------------


@dataclass
class SlokaResult:
    """Model-normalized payload for one sloka."""

    slokam_tamil_script: str
    split_lines: List[str]
    meaning: str


# ---------------------------- Prompt constants -------------------------------


SYSTEM_INSTRUCTIONS = """
You convert Sanskrit Narayaneeyam slokas to Tamil study format.

Return ONLY strict JSON with this exact schema:
{
  "slokam_tamil_script": "string",
  "split_lines": ["string", "..."],
  "meaning": "string"
}

Rules:
- slokam_tamil_script must be fully in Tamil script.
- split_lines must be simple Tamil phrase-level splits.
- meaning must be concise, clear Tamil prose.
- Do not include markdown or extra keys.
""".strip()


# ---------------------------- Input extraction --------------------------------


def split_sloka_blocks(text: str) -> List[str]:
    """Split content into sloka blocks separated by blank lines."""
    blocks = re.split(r"\n\s*\n", text.strip())
    return [b.strip() for b in blocks if b.strip()]


def read_slokas_from_text_files(paths: Sequence[Path]) -> List[str]:
    """Read sloka blocks from UTF-8 text files."""
    blocks: List[str] = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        file_blocks = split_sloka_blocks(content)
        LOGGER.info("Loaded %d sloka block(s) from text file: %s", len(file_blocks), path)
        blocks.extend(file_blocks)
    return blocks


def read_slokas_from_pdf_files(paths: Sequence[Path]) -> List[str]:
    """Extract text from PDF files and split into sloka blocks.

    This is heuristic extraction intended as a practical starting point.
    """
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError(
            "PDF input requires 'pypdf'. Install dependencies from requirements.txt"
        ) from exc

    blocks: List[str] = []
    for path in paths:
        reader = PdfReader(str(path))
        raw_pages: List[str] = []
        for page in reader.pages:
            raw_pages.append(page.extract_text() or "")

        pdf_text = "\n\n".join(raw_pages)
        normalized = re.sub(r"\r\n?", "\n", pdf_text)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        file_blocks = split_sloka_blocks(normalized)
        LOGGER.info("Loaded %d sloka block(s) from PDF file: %s", len(file_blocks), path)
        blocks.extend(file_blocks)

    return blocks


def collect_input_slokas(text_files: Sequence[Path], pdf_files: Sequence[Path]) -> List[str]:
    """Load sloka blocks from all supported input types."""
    all_blocks: List[str] = []
    if text_files:
        all_blocks.extend(read_slokas_from_text_files(text_files))
    if pdf_files:
        all_blocks.extend(read_slokas_from_pdf_files(pdf_files))
    return all_blocks


# ---------------------------- OpenAI + parsing --------------------------------


def build_user_prompt(sloka_text: str, title: str | None = None) -> str:
    """Create a user prompt for one sloka."""
    title_part = f"Context title: {title}\n" if title else ""
    return f"{title_part}Convert this Sanskrit sloka:\n\n{sloka_text.strip()}\n"


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Parse JSON robustly from model output text."""
    data = text.strip()

    # Direct JSON
    try:
        obj = json.loads(data)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # JSON fenced block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", data, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # First object-shaped substring
    start, end = data.find("{"), data.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = data[start : end + 1]
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj

    raise ValueError("Unable to parse JSON object from model output.")


def normalize_result(raw: dict[str, Any]) -> SlokaResult:
    """Validate and normalize a decoded JSON payload."""
    slokam = str(raw.get("slokam_tamil_script", "")).strip()
    meaning = str(raw.get("meaning", "")).strip()
    split_raw = raw.get("split_lines", [])

    if not isinstance(split_raw, list):
        split_raw = [str(split_raw)] if split_raw else []

    split_lines = [str(item).strip() for item in split_raw if str(item).strip()]

    if not slokam:
        raise ValueError("Missing slokam_tamil_script")
    if not split_lines:
        raise ValueError("Missing split_lines")
    if not meaning:
        raise ValueError("Missing meaning")

    return SlokaResult(slokam_tamil_script=slokam, split_lines=split_lines, meaning=meaning)


def get_openai_client() -> Any:
    """Initialize OpenAI client lazily so non-API commands still work."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(
            "OpenAI SDK is not available. Install dependencies from requirements.txt"
        ) from exc

    return OpenAI(api_key=api_key)


def response_to_text(response: Any) -> str:
    """Extract text from a Responses API payload with multiple fallbacks."""
    output_text = getattr(response, "output_text", "") or ""
    if output_text.strip():
        return output_text.strip()

    chunks: List[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            # SDK may expose text on .text or inside .text.value
            text_direct = getattr(content, "text", None)
            if isinstance(text_direct, str) and text_direct.strip():
                chunks.append(text_direct)
                continue
            value = getattr(text_direct, "value", None)
            if isinstance(value, str) and value.strip():
                chunks.append(value)

    joined = "\n".join(chunks).strip()
    if not joined:
        raise ValueError("Empty model response text.")
    return joined


def is_insufficient_quota_error(exc: Exception) -> bool:
    """Return True if exception indicates OpenAI insufficient quota."""
    code = str(getattr(exc, "code", "") or "").strip().lower()
    if code == "insufficient_quota":
        return True

    message = str(exc).lower()
    return "insufficient_quota" in message or "exceeded your current quota" in message


def convert_sloka_with_model(client: Any, model: str, sloka: str, title: str | None) -> SlokaResult:
    """Convert one sloka through the Responses API."""
    prompt = build_user_prompt(sloka, title)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    text = response_to_text(response)
    raw = extract_json_from_text(text)
    return normalize_result(raw)


# ---------------------------- Rendering --------------------------------------


def render_tamil_output(results: Sequence[SlokaResult], title: str | None = None) -> str:
    """Render output in the exact required Tamil study layout."""
    rows: List[str] = []

    if title:
        rows.extend([title, ""])

    for idx, result in enumerate(results, start=1):
        rows.extend(
            [
                f"🔹 ஸ்லோகம் {idx}",
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

    return "\n".join(rows).rstrip() + "\n"


def chunked(seq: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    """Yield chunks from sequence."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# ---------------------------- Pipeline ---------------------------------------


def process(
    text_files: Sequence[Path],
    pdf_files: Sequence[Path],
    output_file: Path,
    title: str | None,
    model: str,
    chunk_size: int,
) -> None:
    """Load inputs, call model, and write output text."""
    slokas = collect_input_slokas(text_files=text_files, pdf_files=pdf_files)
    if not slokas:
        raise ValueError("No sloka blocks found in the provided inputs.")

    client = get_openai_client()
    results: List[SlokaResult] = []

    for group in chunked(slokas, chunk_size):
        for sloka in group:
            try:
                results.append(convert_sloka_with_model(client, model, sloka, title))
            except Exception as exc:
                if is_insufficient_quota_error(exc):
                    raise RuntimeError(
                        "OpenAI API quota exceeded (insufficient_quota). "
                        "Please enable billing or top up credits, then rerun."
                    ) from exc
                LOGGER.error("Failed to process one sloka block: %s", exc)
                results.append(
                    SlokaResult(
                        slokam_tamil_script="[பிழை: ஸ்லோகம் மாற்றம் தோல்வி]",
                        split_lines=["[பிழை: பதவுரை உருவாக்க முடியவில்லை]"],
                        meaning="[பிழை: பொருள் உருவாக்க முடியவில்லை]",
                    )
                )

    output_file.write_text(render_tamil_output(results, title=title), encoding="utf-8")
    LOGGER.info("Wrote %d formatted sloka(s): %s", len(results), output_file)


# ---------------------------- CLI --------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Format Narayaneeyam slokas into Tamil study text using OpenAI Responses API."
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="*",
        default=[],
        help="UTF-8 input text file(s). Separate slokas using blank lines.",
    )
    parser.add_argument(
        "--input-pdf",
        nargs="*",
        default=[],
        help="Optional PDF input file(s) to extract sloka blocks from.",
    )
    parser.add_argument("-o", "--output", required=True, help="Output .txt file path")
    parser.add_argument("-t", "--title", default="நாராயணீயம் தசகம் 1", help="Optional top title")
    parser.add_argument("-m", "--model", default="gpt-4.1-mini", help="OpenAI model")
    parser.add_argument("-c", "--chunk-size", type=int, default=3, help="Slokas per processing chunk")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def validate_paths(paths: Sequence[Path], label: str) -> None:
    """Raise if any path in sequence is missing."""
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing {label} file(s): {', '.join(missing)}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    text_files = [Path(p) for p in args.input]
    pdf_files = [Path(p) for p in args.input_pdf]
    output_file = Path(args.output)

    if not text_files and not pdf_files:
        LOGGER.error("Provide at least one input via --input and/or --input-pdf")
        return 2
    if args.chunk_size <= 0:
        LOGGER.error("--chunk-size must be greater than 0")
        return 2

    try:
        validate_paths(text_files, "text input")
        validate_paths(pdf_files, "PDF input")
        process(
            text_files=text_files,
            pdf_files=pdf_files,
            output_file=output_file,
            title=args.title,
            model=args.model,
            chunk_size=args.chunk_size,
        )
        return 0
    except Exception as exc:
        LOGGER.error("Processing failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
