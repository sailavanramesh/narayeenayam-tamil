# narayaneeyam-formatter

Python project to convert Sanskrit **Narayaneeyam** slokas from UTF-8 `.txt` input into Tamil study text layout using the **OpenAI Python SDK** and **Responses API**.

## Features

- Python 3.10+
- Reads one or more input files
- Treats each slokam block as text separated by a blank line
- Produces plain `.txt` output in the exact Tamil study layout:

```text
🔹 ஸ்லோகம் X
📖 ஸ்லோகம் (தமிழ் எழுத்து)

<full sloka in Tamil script>

✨ பதவுரை (Split)

<easy Tamil split lines>

🌼 பொருள்

<simple Tamil meaning>
```

- Modular and commented code
- CLI options for `--input`, `--output`, `--title`, `--model`, `--chunk-size`
- Robust JSON parsing with fallback handling for model output quirks
- Starts with Dasakam 1 sample input support

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## Usage

### Basic

```bash
python narayaneeyam_formatter.py \
  --input sample_narayaneeyam_d1_input.txt \
  --output dasakam1_tamil_output.txt
```

### With custom title/model/chunk-size

```bash
python narayaneeyam_formatter.py \
  --input sample_narayaneeyam_d1_input.txt \
  --output dasakam1_tamil_output.txt \
  --title "நாராயணீயம் தசகம் 1" \
  --model "gpt-4.1-mini" \
  --chunk-size 2
```

### Multiple input files

```bash
python narayaneeyam_formatter.py \
  --input sample_narayaneeyam_d1_input.txt more_slokas.txt \
  --output combined_output.txt
```

## Input format

- UTF-8 text files
- One slokam block per paragraph
- Separate each slokam block with a blank line

## Notes

- If model output is malformed, the script uses JSON extraction fallbacks.
- If an individual sloka fails, the script inserts a Tamil error placeholder and continues.
- You can later add PDF extraction as a pre-processing stage (e.g., extract Sanskrit + commentary text into block format before running this formatter).
