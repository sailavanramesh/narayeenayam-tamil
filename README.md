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


## Quick start (macOS zsh)

If your prompt looks like `base) ...$`, you are in the **shell** (good).
If your prompt looks like `>>>`, you are inside **Python REPL** (wrong place for shell commands).

Use these exact commands in terminal:

```bash
cd /path/to/narayeenayam-tamil
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
python narayaneeyam_formatter.py --input sample_narayaneeyam_d1_input.txt --output out.txt
```

If you accidentally entered Python (`>>>`), exit first:

```python
exit()
```

Then run shell commands again at `$` prompt.

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
- If one sloka fails conversion (non-quota errors), the script inserts Tamil error placeholders and continues.
- If the API returns `insufficient_quota`, the script now stops immediately with a clear error and does **not** write a placeholder-only output file.
- PDF parsing quality depends on source PDF text layer quality; OCR PDFs may need pre-cleaning.

## Quota error (`429 insufficient_quota`) quick fix

If you see:

- `Error code: 429`
- `insufficient_quota`

then your API project currently has no usable credits/quota.

1. Open: https://platform.openai.com/settings/organization/billing/overview
2. Ensure billing is active and a payment method is set.
3. If needed, add credits / raise hard limit.
4. Re-run the same command.
