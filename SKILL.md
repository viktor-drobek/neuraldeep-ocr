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
    requires_file: "~/.coddy/providers/neuraldeep/neuraldeep-auth.json"
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

### Primary key source
```bash
~/.coddy/providers/neuraldeep/neuraldeep-auth.json
```
Extract: `jq -r '.api_key' ~/.coddy/providers/neuraldeep/neuraldeep-auth.json`

### Fallback
```bash
${NEURALDEEP_API_KEY}
```

### Resolve key helper
```bash
ND_KEY=$(jq -r '.api_key' ~/.coddy/providers/neuraldeep/neuraldeep-auth.json 2>/dev/null)
[ -z "$ND_KEY" ] && ND_KEY="${NEURALDEEP_API_KEY}"
```
If empty → `BLOCKED` + suggest `coddy providers login neuraldeep`.

## Base URL

```
https://api.neuraldeep.ru/v1/ocr
```

---

## 1. Submit Document for OCR

Upload a file and get a `job_id`. Processing is **asynchronous**.

### curl example (fast, default)
```bash
ND_KEY=$(jq -r '.api_key' ~/.coddy/providers/neuraldeep/neuraldeep-auth.json 2>/dev/null || echo "${NEURALDEEP_API_KEY}")
curl -sS -X POST "https://api.neuraldeep.ru/v1/ocr/extract" \
  -H "Authorization: Bearer ${ND_KEY}" \
  -F "file=@invoice.pdf"
```

### curl example (pro profile — higher quality)
```bash
curl -sS -X POST "https://api.neuraldeep.ru/v1/ocr/extract" \
  -H "Authorization: Bearer ${ND_KEY}" \
  -F "file=@invoice.pdf" \
  -F "model_profile=pro"
```

### curl example (page range)
```bash
curl -sS -X POST "https://api.neuraldeep.ru/v1/ocr/extract" \
  -H "Authorization: Bearer ${ND_KEY}" \
  -F "file=@report.pdf" \
  -F 'page_ranges=[{"start":1,"end":5}]'
```

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
ND_KEY=$(jq -r '.api_key' ~/.coddy/providers/neuraldeep/neuraldeep-auth.json 2>/dev/null || echo "${NEURALDEEP_API_KEY}")
JID="job_abc123"
curl -sS "https://api.neuraldeep.ru/v1/ocr/jobs/${JID}" \
  -H "Authorization: Bearer ${ND_KEY}"
```

**Response:**
```json
{"id": "job_abc123", "status": "pending | processing | completed | failed", ...}
```

**Polling interval:** every 1 second.

---

## 3. Fetch Result

### Default JSON
```bash
curl -sS "https://api.neuraldeep.ru/v1/ocr/jobs/job_abc123/result" \
  -H "Authorization: Bearer ${ND_KEY}"
```

### Markdown format
```bash
curl -sS "https://api.neuraldeep.ru/v1/ocr/jobs/job_abc123/result?format=markdown" \
  -H "Authorization: Bearer ${ND_KEY}"
```

### Text format
```bash
curl -sS "https://api.neuraldeep.ru/v1/ocr/jobs/job_abc123/result?format=text" \
  -H "Authorization: Bearer ${ND_KEY}"
```

**Response shape (JSON):**
```json
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
curl -sS "https://api.neuraldeep.ru/v1/ocr/balance" \
  -H "Authorization: Bearer ${ND_KEY}"
```

**Response (проверено):**
```json
{"entity_code": "scan_page", "remaining_pages": 1500, "total_affordable_pages": 1500,
 "monthly_pages": {"total": 1500, "allocated": 0, "remaining": 1500},
 "daily_pages": {"total": 100, "allocated": 0, "remaining": 100},
 "tier": "starter"}
```

---

## Complete Python Example

```python
import time, httpx, json, os

BASE = "https://api.neuraldeep.ru/v1"
KEY = json.load(open(os.path.expanduser(
    "~/.coddy/providers/neuraldeep/neuraldeep-auth.json"
)))["api_key"]
H = {"Authorization": f"Bearer {KEY}"}

# 1. Upload
with open("invoice.pdf", "rb") as f:
    job = httpx.post(
        f"{BASE}/ocr/extract",
        headers=H,
        files={"file": ("invoice.pdf", f, "application/pdf")},
        data={"model_profile": "pro"},
    ).json()

jid = job["id"]
print("pages:", job["page_count"], "charged:", job["scan_pages_charged"])

# 2. Poll
for _ in range(300):
    st = httpx.get(f"{BASE}/ocr/jobs/{jid}", headers=H).json()
    if st["status"] == "completed":
        break
    if st["status"] == "failed":
        raise RuntimeError("OCR failed")
    time.sleep(1)

# 3. Fetch markdown
res = httpx.get(f"{BASE}/ocr/jobs/{jid}/result", params={"format": "markdown"}, headers=H).json()
print(res["content"])
```

---

## Workflow Summary

1. Resolve key
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
- `500`/`503` — transient error → retry after delay

## Privacy & Security

- Do not upload documents containing third-party PII without user consent.
- OCR processing happens on NeuralDeep infrastructure (data does not leave the provider).
- Anonymize before upload when possible (see PII Guard skill `/v1/pii/anonymize`).
