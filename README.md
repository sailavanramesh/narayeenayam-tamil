# narayaneeyam-formatter

Convert Sanskrit **Narayaneeyam** slokas into Tamil study text with this exact layout:

```text
🔹 ஸ்லோகம் X
📖 ஸ்லோகம் (தமிழ் எழுத்து)

<full sloka in Tamil script>

✨ பதவுரை (Split)

<easy Tamil split lines>

🌼 பொருள்

<simple Tamil meaning>
```

The project uses the **OpenAI Python SDK** + **Responses API** and supports input from:

- UTF-8 `.txt` files (sloka blocks separated by blank lines)
- PDF files (heuristic text extraction)

## Requirements

- Python 3.10+
- `OPENAI_API_KEY` environment variable

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
```

## Usage

### 1) Text input only

```bash
python narayaneeyam_formatter.py \
  --input sample_narayaneeyam_d1_input.txt \
  --output dasakam1_tamil_output.txt
```

### 2) PDF input only

```bash
python narayaneeyam_formatter.py \
  --input-pdf narayaneeyamAllDashakas.pdf \
  --output all_dashakas_tamil_output.txt \
  --title "நாராயணீயம்"
```

### 3) Mix text + PDF inputs

```bash
python narayaneeyam_formatter.py \
  --input sample_narayaneeyam_d1_input.txt \
  --input-pdf narayaneeyamAllDashakas.pdf \
  --output combined_tamil_output.txt \
  --model gpt-4.1-mini \
  --chunk-size 2
```

## CLI options

- `-i, --input` : one or more UTF-8 text files
- `--input-pdf` : one or more PDF files
- `-o, --output` : output `.txt` file
- `-t, --title` : optional heading/title at top
- `-m, --model` : OpenAI model (default: `gpt-4.1-mini`)
- `-c, --chunk-size` : number of slokas processed per loop (default: `3`)
- `--log-level` : `DEBUG|INFO|WARNING|ERROR`

## Notes

- JSON parsing is intentionally defensive (direct JSON, fenced JSON, object slice fallback).
- If one sloka fails conversion, the script inserts Tamil error placeholders and continues.
- PDF parsing quality depends on source PDF text layer quality; OCR PDFs may need pre-cleaning.
