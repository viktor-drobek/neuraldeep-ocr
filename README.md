# 📄 neuraldeep-ocr

OCR and document extraction from PDFs and images (PNG/JPG/WEBP/BMP/TIFF) with fast/pro profiles, page ranges, and markdown/JSON/text output.

A [Coddy](https://coddy.dev) / AI-agent skill for the **NeuralDeep OCR API**.

## Author

**Viktor Drobek**

## Install

```bash
# via the skillsbd catalog
npx skillsbd add viktor-drobek/neuraldeep-ocr/neuraldeep-ocr

# or directly from this repo
npx skillsbd add https://github.com/viktor-drobek/neuraldeep-ocr --skill neuraldeep-ocr
```

## Requirements

- A NeuralDeep API key (`sk-...`) in this skill's own variable `NEURALDEEP_OCR_API_KEY` (several
  keys may be separated by commas), or the shared `NEURALDEEP_API_KEY`, set in the
  environment or in `${CODDY_HOME:-~/.coddy}/.env`:

  ```bash
  echo 'NEURALDEEP_OCR_API_KEY=sk-...' >> ~/.coddy/.env
  ```
- Python 3.10+ (standard library only).
- Get a key at <https://neuraldeep.ru> (Hub).

## Usage

See [`SKILL.md`](./SKILL.md) for the full API reference, endpoints, request/response
shapes, and worked examples.

## Starter guard and Relay handoff

See [STARTER_RELAY.md](./STARTER_RELAY.md) for guarded commands, private job
state, timeout recovery, and the optional artifact-based Relay envelope.
The helper checks live service quota rather than hard-coding daily limits.

Run offline tests: `python3 -B -m unittest discover -s tests`.

## License

[MIT](./LICENSE)
