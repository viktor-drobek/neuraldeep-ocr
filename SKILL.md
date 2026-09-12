---
name: neuraldeep-ocr
description: >
  OCR and document extraction skill powered by NeuralDeep OCR API.
  Extracts text from PDFs and images (PNG/JPG/WEBP/BMP/TIFF) asynchronously.
  Supports fast and pro profiles, page ranges, markdown/JSON/text output formats,
  and coordinate-based bounding boxes.
  Automatically activates when user asks for OCR, PDF text extraction,
  document parsing, or reading scanned pages.
metadata:
  neuraldeep:
    emoji: "📄"
    base_url: "https://api.neuraldeep.ru/v1/ocr"
    endpoints:
      - /v1/ocr/extract
      - /v1/ocr/jobs/{id}
      - /v1/ocr/jobs/{id}/result
      - /v1/ocr/balance
---

> **Author:** these skills were authored by the **kimi2.6** and **qwen3.8 27b** models, and are published by **viktor-drobek**.

# NeuralDeep OCR

Use this skill whenever the user needs:
- Extracting text from PDF documents
- OCR on images containing text (scans, receipts, invoices)
- Converting scanned documents to markdown
- Processing documents with page-range filters
- Recognizing text with layout preservation

## Requirements

Python 3.10+ is sufficient; the helper uses only the standard library.
Run commands from this skill's directory. No `curl`, `jq`, or `httpx` is required.

The helper first reads `api_key` from
`${CODDY_HOME:-~/.coddy}/providers/neuraldeep/neuraldeep-auth.json`, then falls
back to `NEURALDEEP_API_KEY` for missing, malformed, null, or empty file values.
It never prints the key. If neither source works, it returns `blocked`; use
`coddy providers login neuraldeep` or supply the environment variable securely.
Do not use `jq -r .api_key` as a presence check: JSON null becomes the string `null`.

Read [Starter and Relay safety](STARTER_RELAY.md) before submitting work.
Every billed operation must pass the helper's live subscription, public-price,
and service-quota checks. A chat `decision.can_request=false` is not a service
quota decision. State files and artifacts are private runtime data, not repo files.

## Base URL

```
https://api.neuraldeep.ru/v1/ocr
```

---

## 1. Submit Document for OCR

Upload a file and get a `job_id`. Processing is **asynchronous**.

### Guarded helper example (fast, default)
```bash
# This example assumes invoice.pdf has exactly one page. Verify locally first.
python3 scripts/client.py run extract --file invoice.pdf --pages 1 --state fast-state.json --output fast-result.json
```

### Guarded helper example (pro profile — higher quality)
```bash
# pro charges two quota pages per input page.
python3 scripts/client.py run extract --file invoice.pdf --pages 1 --profile pro --state pro-state.json --output pro-result.json
```

### Guarded helper example (page range)
The API accepts `page_ranges`; the minimal helper does not yet encode this field.
Select the required pages locally into a separate PDF, verify its page count,
and pass that file with `--pages`. Never guess a PDF's page count.

**Supported formats:** PDF, PNG, JPG, WEBP, BMP, TIFF

**Form fields (multipart):**
- `file` (file, required) — the document or image
- `model_profile` (string, optional) — `fast` (default) or `pro`
  - `pro` counts as **2 pages per sheet** and yields higher recognition quality (recommended for complex layouts, tables, handwriting)
- `page_ranges` (JSON string, optional) — array of `{"start": N, "end": M}` objects to process only specific pages

**Response:**
```json
{"id": "job_abc123", "page_count": 12, "scan_pages_charged": 12}
```

---

## 2. Poll Job Status

```bash
# Only after a prior run timed out or had a transient polling error:
python3 scripts/client.py resume --state fast-state.json --output fast-result.json --timeout 300
```

**Response:**
```text
{"id": "job_abc123", "status": "pending | processing | completed | failed", ...}
```

**Polling interval:** every 1 second.

---

## 3. Fetch Result

### Default JSON
The API endpoint is `GET /v1/ocr/jobs/{id}/result`. Fetch only after confirmed
completion. The helper saves the markdown-format JSON response as an artifact.

### Markdown format
`GET /v1/ocr/jobs/{id}/result?format=markdown` is the helper's result endpoint.
Read its `content` field only after the helper reports `completed`.

### Text format
The API also offers `GET /v1/ocr/jobs/{id}/result?format=text`; custom callers
must use the same bounded polling and error handling before fetching it.

**Response shape (JSON):**
```text
{
  "id": "job_abc123",
  "content": "Extracted markdown text...",
  "pages": [
    {"page": 1, "text": "...", "bboxes": [{"text": "...", "x": 10, "y": 20, "w": 100, "h": 30}]}
  ]
}
```

---

## 4. Check Remaining OCR Balance

```bash
python3 scripts/client.py check extract --pages 1 --profile pro
```

**Verified quota structure:** `GET /v1/ocr/balance` returns `tier`,
`daily_pages.remaining`, and `monthly_pages.remaining`, alongside aggregate
page fields. The helper requires both windows to cover the verified input
page count, doubled for `pro`. Do not use aggregate affordable pages as a
substitute for the daily and monthly subscription buckets.

---

## Complete Python Example

```python
import json
from pathlib import Path
import subprocess
# Verify that this input has one page before running.
subprocess.run(["python3", "scripts/client.py", "run", "extract", "--file", "invoice.pdf",
                "--pages", "1", "--profile", "pro", "--state", "python-ocr-state.json",
                "--output", "ocr-result.json", "--timeout", "300"], check=True)
data = json.loads(Path("ocr-result.json").read_text())
print(data["content"])
```

---

## Workflow Summary

1. Resolve key and pass the live Starter guard
2. **POST `/ocr/extract`** with file (and optional `model_profile=pro`, `page_ranges`) → get `job_id`
3. **Poll `/ocr/jobs/{id}`** until `status == completed`
4. **GET `/ocr/jobs/{id}/result`** (JSON/md/text)

## Cost & Limits

- Counted in **pages** (not requests).
- Available on **all tariffs** (free, starter, pro).
- `fast` = 1 page per sheet; `pro` = 2 pages per sheet (higher accuracy).
- Status polling and result fetching do **not** consume quota.

## Error Handling

- `401` — invalid key
- `429` — page quota exhausted
- `400` — unsupported file format or malformed page_ranges
- `500`/`503` — stop; reconcile an uncertain submission instead of retrying it

## Privacy & Security

- Do not upload documents containing third-party PII without user consent.
- OCR inputs leave the local machine and are processed on provider infrastructure; review provider privacy terms before upload.
- Anonymize before upload when possible (see PII Guard skill `/v1/pii/anonymize`).
