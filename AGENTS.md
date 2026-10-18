# Agent instructions

For coding agents working in this repository (Codex, Coddy and others).
User-facing docs: [README.md](README.md), [SKILL.md](SKILL.md),
[STARTER_RELAY.md](STARTER_RELAY.md); test history: [TESTING.md](TESTING.md).

## What this is

An agent skill for the NeuralDeep OCR API. The only code is
`scripts/client.py`: a standard-library-only Python 3.10+ helper with a
fail-closed Starter subscription guard, durable job state and resumable polling.
There are no dependencies to install.

## The helper is shared

`scripts/client.py` is kept identical across the neuraldeep-search, -images,
-ocr, -speechcore, -transcriptions and -diarization repositories, apart from the `SERVICE = ...`
line. Code paths for other services exist here but run only in tests.

- Do not change behaviour for one service only; a fix belongs in every repo.
- Compare with a sibling checkout before and after an edit:

```bash
diff <(grep -v '^SERVICE = ' scripts/client.py) <(grep -v '^SERVICE = ' ../neuraldeep-search/scripts/client.py)
```

Once a change has landed in every repo this prints nothing. Output means a port
is pending in one direction or the other: find out which before editing, and
never overwrite a sibling's newer change with an older copy.

## Safety contract

- Never call a billed endpoint, submit a job or use a real API key in tests or
  while developing. Tests use mocked HTTP and synthetic fixtures only.
- Fail closed: anything unexpected ends in `blocked`, never in a submission.
- Never retry or resubmit a POST. An ambiguous submission is
  `reconciliation_required`; keep the provider job ID.
- Never print or store the key, authorization headers or provider response
  bodies. Error text stays sanitized.
- SpeechCore uploads and whisper-1 transcription stay blocked until a
  remaining-quota endpoint is verified.
- Do not commit runtime state, inputs, results, `.env` files or secrets.

## Tests

Run all three before every commit; each must pass with 0 warnings:

```bash
python3 -X dev -W error::ResourceWarning -B -m unittest discover -s tests
```

```bash
env LC_ALL=C LANG=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 python3 -B -m unittest discover -s tests
```

```bash
python3 -X warn_default_encoding -B -m unittest discover -s tests
```

- Work test-first: add a test, see it fail for the expected reason, then fix.
  For tests that pin existing behaviour, break the code in a scratch copy and
  confirm the test catches it.
- Pass `encoding="utf-8"` to every text-mode read, write and subprocess call.
- `tests/test_examples.py` parses the fenced `python` and `bash` blocks in
  README.md, SKILL.md and STARTER_RELAY.md, and checks that the polling
  interval and default `--timeout` in SKILL.md match the helper.
- Record each change in TESTING.md: what failed first, and the new test count.

## Delivery workflow

Work RED-GREEN-REFACTOR: start a feature with a test that describes the observable result and a
bug fix with a regression test, watch it fail for the intended reason, make the smallest change
that passes, and refactor only with the suite green. Then run the full offline matrix above.

Inside `scripts/client.py`, implement from lower dependencies upward: constants and parsing,
credentials and approved-origin transport, the fail-closed guard, durable state and artifacts,
provider jobs and polling, then `execute()` and the CLI. Lower layers must not depend on CLI
parsing or provider job state.

Update `README.md`, `SKILL.md`, `STARTER_RELAY.md` and `TESTING.md` in the same change when
behavior, CLI output, safety assumptions or documented shapes change.

## Rules Sync

This file is the common policy for every agent, and `CLAUDE.md` is a symlink to it. Scoped detail
lives in native rules with identical bodies:

| Rule | Scope | Cursor | Claude Code |
|---|---|---|---|
| `workflow` | always on | `.cursor/rules/workflow.mdc` | `.claude/rules/workflow.md` |
| `client` | `scripts/**/*.py`, `tests/test_client.py` | `.cursor/rules/client.mdc` | `.claude/rules/client.md` |
| `documentation` | `README.md`, `SKILL.md`, `STARTER_RELAY.md`, `TESTING.md`, `tests/test_examples.py` | `.cursor/rules/documentation.mdc` | `.claude/rules/documentation.md` |

- Cursor reads `.cursor/rules/`; Claude Code reads `CLAUDE.md` and `.claude/rules/`.
- Codex reads this file, and the project hook in `.codex/hooks.json` with
  `.codex/hooks/attach_rules.py` attaches the Cursor rules: always-on rules at session start,
  scoped rules before an edit to a matching file. Run `/hooks` in Codex once per clone and again
  after changing either hook file. The hook is a fail-open convenience, not a security boundary;
  the safety rules here, the helper and the tests still enforce them.
- Never copy rule bodies under `.codex` or create `.codex/rules.md`.
- Change a rule and its counterpart together. `tests/test_agent_rules.py` checks the pairing, the
  scopes and the hook; it and `.codex/hooks/` are identical across the neuraldeep-* repositories.

## Releases

A release is a `vX.Y.Z` tag on `main` with a GitHub release. `metadata.version` in the `SKILL.md`
frontmatter is the version Coddy shows and uses to decide whether an installed copy is older, so
it must equal the tag without the `v`:

1. In a PR, bump `metadata.version` (semantic versioning) and note the change in `TESTING.md`.
2. After the PR is merged and CI is green, tag the merge commit and publish the release, for
   example `gh release create v1.0.0 --target main --title v1.0.0 --notes-file NOTES.md`.
3. CI runs on the tag push; `tests/test_release.py` fails the build if the tag and
   `metadata.version` differ. It is identical across the neuraldeep-* repositories.

## Git workflow

- Never commit or push to `main`. Use a branch and open a pull request;
  merging is the user's decision.
- Several agent sessions may share this checkout. Check `git status` and the
  current branch before you start, and touch only your own branch.
- Do not rewrite history, force-push, or delete branches unless the user asks.
- No AI attribution: no `Co-Authored-By` trailers for agents in commits and
  no "Generated with ..." lines in pull requests.
- CI (`.github/workflows/tests.yml`) runs the offline suite on Python 3.10 and
  3.x; it must pass before merging.
