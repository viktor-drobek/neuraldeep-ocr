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
  version: 2.0.0
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

The helper reads the key from `NEURALDEEP_OCR_API_KEY`, this skill's own variable, then
from the shared `NEURALDEEP_API_KEY`. Each is taken from the environment first,
then from `${CODDY_HOME:-~/.coddy}/.env`, the file Coddy loads at startup, so
a key added there works without a restart. A variable may hold several keys
separated by commas: before a billed request the helper uses the first key
whose free subscription and quota checks pass, and records its number (never
the key) in the state, so `resume` uses the same key. The Coddy provider file
is not read. The helper never prints a key. Without one it returns `blocked`,
naming the variable: ask the user to add it to `~/.coddy/.env` themselves,
for example `NEURALDEEP_OCR_API_KEY=sk-...`, never in the chat.

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

**Polling interval:** the helper checks status every 2 seconds until its polling
deadline; `--timeout` defaults to 120 seconds. Examples that pass `--timeout 300`
extend that deadline for larger documents.

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

## Paying from the wallet

A NeuralDeep key pays either from a subscription or from the rouble wallet, never
both (the mode is switched per key at <https://hub.neuraldeep.ru/app/keys>). In
wallet mode the subscription quota does not apply and every operation costs money
at the public price list. The helper therefore:

- prefers a subscription key: with several keys, a wallet key is considered only
  when no subscription key passes its quota check;
- never spends from the wallet on its own. `check` and `run` end with the status
  `wallet_approval_required`, the price, the estimated cost (the quota units times
  the price, rounded up to whole kopecks) and the wallet balance, for example:

  ```text
  Key 1 of NEURALDEEP_API_KEY pays from the wallet, not a subscription: about 1.00 RUB
  (1 x 1 RUB for ocr:extract), wallet balance 370.05 RUB. Ask the user whether to pay;
  only after a clear yes, run again with --wallet-limit 1.00
  ```
- pays only with `--wallet-limit RUB`, the roubles the user approved for this run,
  and blocks before any request when the estimate exceeds that limit, the wallet
  balance, or the key's own spending cap.

**Show the warning to the user and wait for an explicit yes to that amount.**
Never pass `--wallet-limit` on your own, never raise an approved amount, and treat
a "no" or no answer as the end of the task. After a yes, run the same command as `run` with `--wallet-limit` set to the approved amount.
The estimate uses the public price list and the same units as the quota; the
provider may round or count differently, so it is an estimate, not an invoice.

```bash
python3 scripts/client.py check extract --pages 1
```

## Error handling

The helper explains an HTTP error with a fixed text for its status, never the
provider's response body, and adds `Retry-After` (whole seconds) and `X-Window`
(`session` or `week`) when the provider sends well-formed values, for example
`HTTP 429 (quota or rate limit reached); retry after 30 s; window week; no
automatic retry`. It never retries by itself. What a failure means depends on
when it happens:

- during the preflight GETs, before anything is billed: `blocked`;
- on the billed submission: `reconciliation_required`, since the work may have
  been charged; reconcile with the provider's records, never submit blindly again;
- while polling an existing job: `poll_error`; resume the same job later.

| Code | What the provider documents | What to do |
|---|---|---|
| `400` | Invalid request body, or a request longer than allowed | Fix the input; a billed submission is reconciled first |
| `401` | Key invalid or revoked, or not subscribed to the model | Ask the user to check the key in `NEURALDEEP_OCR_API_KEY` (or `NEURALDEEP_API_KEY`) in the environment or `~/.coddy/.env`; never read the file yourself |
| `408` | Upstream timeout after the provider's own retries | Reconcile a submission; resume a job |
| `422` | A parameter outside the allowed values | Fix the parameter |
| `429` | A quota or rate limit; `X-Window` names the session or week window and `Retry-After` the wait | Check the quota with `check`; wait, then decide explicitly |
| `500` | Internal error; the provider suggests repeating | Reconcile a submission before any new one; resume a job |
| `502` | Upstream unavailable; usually passes on its own | Reconcile or resume as above |
| `503` | Temporarily unavailable, with `Retry-After` | Wait; reconcile or resume as above |

Any other status is reported as `HTTP <code>` without a hint. A transport
failure or an unreadable answer is `Transport or response error`, with the same
outcomes.

- `400` can also mean an unsupported file format.
- `429` on OCR means the page quota is spent; `check extract --pages N` shows what is left.

## Privacy & Security

- Do not upload documents containing third-party PII without user consent.
- OCR inputs leave the local machine and are processed on provider infrastructure; review provider privacy terms before upload.
- Anonymize before upload when possible (see PII Guard skill `/v1/pii/anonymize`).
