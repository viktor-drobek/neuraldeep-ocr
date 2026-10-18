# Test-first verification

No billed endpoint was called during development or verification. Publication is separate from these test results.

## Red/green sequence

1. Added `tests/test_client.py` before `scripts/client.py` existed. Running
   `python3 -B -m unittest discover -s tests` failed with a missing-helper
   `FileNotFoundError` in each of the four service repositories.
2. Implemented the helper. The original nine safety tests passed in each repo.
3. Added six regression/workflow tests. The shared suite exposed two failures:
   result download could start after a just-expired polling deadline, and a
   preflight HTTP error was mislabeled `poll_error` instead of `blocked`.
4. Fixed both branches. Added the fenced-example syntax test before creating
   `STARTER_RELAY.md`; it failed because that required guide did not exist.
5. Created the guide and reran the full suite. Final results are reported below
   only after execution; no live submission/result is claimed by offline tests.

## Coverage

- Credential file and environment fallback, null/empty/missing values, CODDY_HOME.
- Starter subscription/status guard, exact non-premium operation, malformed and
  insufficient service quota, independent chat decision, double-page OCR pro cost.
- HTTP failures and ambiguous submissions with no retry or secret disclosure.
- Durable provider ID before polling; duplicate state creation refused.
- Failed statuses and deadline exhaustion never fetch results; unknown statuses keep polling.
- SHA-256 artifact provenance and untrusted-data labeling.
- Python and Bash fenced examples parsed without execution.

Official documentation and documented read-only quota endpoints were inspected;
only schema structure and public operation classification informed the fixtures.
SpeechCore remaining quota is unverified, so upload remains blocked. No end-to-end
paid test was performed. Artifact formats and submission contracts follow provider
documentation; the tests exercise mocked responses, not a claim of live success.

A further regression test exposed a CLI catch-all that hid sanitized block
reasons; it was fixed. A mocked workflow test covers all five image operations
as asynchronous jobs, including multipart processing rather than direct PNG POSTs.

## Unknown polling status

A live run on 2026-10-17 (four agents, real API) found that every OCR `run extract`
ended `failed` with "returned an unknown status", although the job had finished:
a later `GET /v1/ocr/jobs/{id}` said `completed`, and `resume` fetched the text.
`poll()` treated any status outside its fixed in-progress list as a failure.

Six tests were added first and failed: an unknown intermediate status now keeps
polling, an unknown status until the deadline ends `timed_out` naming it (only a
plain word is echoed), explicit failure statuses still stop at once, a response
without a status is a resumable `poll_error`, and a mocked OCR run passes through
an unknown status to `completed`. Mutations of the failure set, the status check
and the sanitising each fail their own test. **48 tests passed**, both normally
and with `LC_ALL=C PYTHONUTF8=0`, with no EncodingWarnings.

## Transcription models

The shared helper now knows three speech-to-text models for the `whisper`
service: `gigaam-v3` (the default), `whisper-1` and `whisper-podlodka-turbo`,
chosen with `--model`. Each has its own public price ID; the guard checks the
chosen model's row and its block names the model. `--model` is refused for the
other services and for unknown models (exit 2). Five shared tests were added
first; four failed and the fifth guards the new flag. Moving the default from
`whisper-1` to `gigaam-v3` updated the tests pinned to it. Mutations of the
default, the model check and the per-model price ID each fail their own test.
A live read-only `check` (2026-10-17) blocked each model at the quota step, so
all three price rows are present and non-premium. **53 tests passed**, both
normally and with `LC_ALL=C PYTHONUTF8=0`.

## Final results

- `python3 -B -m unittest discover -s tests`: **22 tests passed** in this repo.
  The identical shared suite passed in all four service repos (88 total).
- `python3 -B scripts/client.py --help`: passed, with no network call.
- `git diff --check`: passed.
- Fenced Python examples parsed with `ast.parse`; Bash examples passed `bash -n`.
- Live **read-only** CLI preflights returned `ready` for Search, OCR, and Images.
  SpeechCore exited nonzero with `blocked` and the unverified-quota reason.
  No account values were saved in this repository and no provider job was created.

Additional test-first fixes ensured early failures carry the full handoff fields
and interrupted HTTP response bodies become sanitized request errors rather than
uncaught exceptions. Both regressions were observed failing before their fixes.

Independent review found that an async error body could be saved as a completed
artifact. Added failing regressions, then validated PNG MIME/signature and JSON
MIME/result fields before artifact creation. Invalid or empty results now preserve
the provider ID with `poll_error` and no success artifact. PNG signature checks
are not a full image-decoding or visual-quality audit. Generated bytecode caches
are excluded by `.gitignore`. The full 88-test regression passed after these fixes.

## OCR workflow, transport and resume coverage

Eight tests were added and one was updated. Two new tests and the updated one
failed first against the old behavior: a reused state path surfaced only the
generic CLI message, `new_state` leaked a bare `FileExistsError`, and SKILL.md
documented a 1-second polling interval while the helper waits 2 seconds. The helper now blocks with "State file already exists"
without touching the existing state, and SKILL.md documents the helper's real
2-second interval and 120-second `--timeout` default; a test keeps them aligned.

The remaining additions passed on first run and pin existing behavior: a mocked
OCR `run` (multipart `model_profile`, anonymized filename, `id` handling, markdown
result URL, artifact hash), `resume` from an existing state file without preflight
or POST, refusal to resume non-resumable or foreign state, and `request()` through
a fake HTTPS transport (origin allowlist, no redirects for 301/302/303/307/308,
no bearer token on the public prices URL).

A later regression test showed that `request()` left a caught `HTTPError`
response open until garbage collection (a `ResourceWarning` on Python 3.14).
It failed first; the handler now closes the error before raising `RequestError`.

- `python3 -B -m unittest discover -s tests`: **32 tests passed** in this repo at that
  point, including the per-service job-ID test from `main`. The four service repos
  no longer run one identical suite: fixes are ported between them individually,
  so check each repo's own test count rather than assuming they match.

Ported from neuraldeep-images: `multipart()` now keeps only an alphanumeric
file extension (`\.[A-Za-z0-9]{1,10}`) in the `filename=` header, so local
names with quotes, `;` or line breaks cannot inject header text. The
regression `test_multipart_filename_cannot_inject_headers` failed first
(4 injection cases); the suite is now **33 tests**.

Ported from neuraldeep-images (beb9533): the 429 case in the HTTP-error test, an extra `file:///` case in the
origin-allowlist test, and `test_timeout_then_resume_from_saved_state_without_resubmitting`,
`test_multipart_body_format` and `test_image_submission_routing`. Its origin,
bearer, redirect and non-resumable-state checks were already covered here by
stronger OCR tests, so those were not duplicated.
They pin existing behavior, so they passed on first run; each was checked by a
targeted mutation of `client.py` in a scratch copy, which it caught. The images
CI workflow (`.github/workflows/tests.yml`: offline suite and `--help` on Python
3.10 and 3.x, with no credential in the environment) was copied unchanged; the
suite is now **36 tests**.

## UTF-8 file reads

Added `test_text_files_are_read_as_utf8_on_non_utf8_locales` first. It runs the
helper in a C locale, whose default text encoding is ASCII, and failed: an auth
file with a non-ASCII field was reported as having no credential, and a UTF-8
`--payload` or state file raised `UnicodeDecodeError`. The helper and tests now
read and write text as UTF-8 explicitly. **37 tests passed**, both normally and
with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Synchronous-resume guard

Ported from neuraldeep-search (ac7260d). `resume` of a hand-edited state with
status `submitted`, `timed_out` or `poll_error` skipped polling for a
synchronous service and then saved an artifact from unassigned data, raising an
uncaught `UnboundLocalError` instead of printing the JSON envelope. OCR never
runs as Search, so this keeps the shared helper identical rather than fixing a
live crash. `test_resume_of_edited_resumable_state_is_blocked_not_crashed`
patches `SERVICE` to `search` and failed first for all three statuses; a
`SYNCHRONOUS` service set now blocks such resumes up front. `scripts/client.py`
matches neuraldeep-search apart from `SERVICE`. **38 tests passed**, both
normally and with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

`test_resume_of_edited_resumable_state_is_blocked_not_crashed` now also checks
that the hand-edited state file is left byte-for-byte unchanged. Moving the
`SYNCHRONOUS` guard into `execute()`'s `try` block let the `Blocked` handler
overwrite that state while the old test still passed; with the new assertion,
that mutation fails all three statuses. `scripts/client.py` is unchanged; the
suite is still **38 tests**.

## whisper-1 service, blocked

Ported from neuraldeep-whisper-1 (36d8bc4) so the shared helper knows every
service. whisper-1 is billed per minute and has no verified remaining-quota
endpoint, so, like SpeechCore uploads, it is blocked in `guard()` and
`submission()`; its public price ID is `whisper-1`, and it is listed as
synchronous. `test_whisper_is_blocked_without_verified_quota` failed first: the
missing `OPERATIONS` entry surfaced as the generic "Unrecognized ... schema"
block instead of the whisper-1 reason. `scripts/client.py` now matches
neuraldeep-whisper-1 apart from `SERVICE`. The `SYNCHRONOUS` entry and the
`submission()` block are not exercised by a test yet. **39 tests passed**, both
normally and with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Malformed resume state and whisper-1 coverage

Ported from neuraldeep-speechcore a9a8073 by way of neuraldeep-whisper-1
eda8436: `resume` now blocks a state file that is not a JSON object, or whose
`status` is not a string or `errors` not a list, with "State is not resumable".
`test_resume_of_malformed_state_is_blocked_not_crashed` failed first in all five
subtests (four `TypeError`s and one `AttributeError`, since OCR is async).
`test_whisper_is_synchronous_and_refuses_resume` and
`test_whisper_run_is_blocked_before_any_request` close the whisper-1 gap noted
above: removing `whisper` from `SYNCHRONOUS` or the `submission()` block now
fails a test, checked by mutation in a scratch copy. All three tests are copied
verbatim from neuraldeep-whisper-1; `scripts/client.py` matches it apart from
`SERVICE`. **42 tests passed**, both normally and with `LC_ALL=C PYTHONUTF8=0`,
with no `EncodingWarning` under `-X warn_default_encoding`.

## Agent rule surfaces

Added `tests/test_agent_rules.py` (10 tests) before any rule file existed; all
10 failed because `.codex/hooks/attach_rules.py`, the rules and `CLAUDE.md` were
missing. Then added Cursor rules (`.cursor/rules/*.mdc`), their Claude Code
mirrors with identical bodies (`.claude/rules/*.md`), the Codex hook that attaches
the Cursor rules (`.codex/hooks.json`, `.codex/hooks/attach_rules.py`),
`CLAUDE.md` as a symlink to `AGENTS.md`, and the Delivery workflow and Rules Sync
sections in `AGENTS.md`. The tests check the pairing and scope mapping, that
every glob matches a file, and the hook itself: always-on rules at session start,
the client rule once per session for patch add, update, delete and rename and for
`Edit` and `Write`, and fail-open on bad input. Eight mutations (a widened or
narrowed scope, `paths` differing from `globs`, body drift, a missing mirror, a
dead glob, `.codex/rules.md`, a copied `CLAUDE.md`) each failed a test. The test
file and `.codex/hooks/` are identical across the neuraldeep-* repositories.
With the five transcription-model tests merged in parallel,
**63 tests passed**, both normally and with `LC_ALL=C PYTHONUTF8=0`, with no
`EncodingWarning` under `-X warn_default_encoding`.

## Release metadata (v1.0.0)

Added `tests/test_release.py` (3 tests, identical across the neuraldeep-*
repositories) first. Two failed: `SKILL.md` had no `metadata.version` and
`AGENTS.md` had no release steps; the tag check is skipped outside a tag build.
`metadata.version: 1.0.0` is now in the `SKILL.md` frontmatter, the key Coddy
reads (`coddy skills list` showed `1.0.0` for a copy under a scratch
`CODDY_HOME`), and `AGENTS.md` has a Releases section. With
`GITHUB_REF_TYPE=tag`, `GITHUB_REF_NAME=v1.0.0` passed and `v1.0.1` failed.
**66 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Diarization service

Port from neuraldeep-diarization: the shared helper now knows the `diarize`
service (`POST /v1/audio/diarize`, price ID `audio:diarize`). Its quota at
`/v1/audio/diarize/quota` reports `used` and `limit` minutes per `day` and
`month`, verified read-only on 2026-10-18, and the guard requires `limit - used`
to cover `--minutes`, at most 240, with files of at most 500 MB. An offline
`merge` command joins a diarization with a timed transcript. `--minutes` and
`merge` are refused for the other services (exit 2), and this service's
behaviour is unchanged. The 16 shared tests and the merge case of the UTF-8 test
were added first and failed with `KeyError: 'diarize'` and the missing
`merge_transcript`. `STARTER_RELAY.md` lists the diarization bucket.
**82 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Diarization formats and cross-review fixes

Port from neuraldeep-diarization. `merge --format json|vtt|srt|rttm` writes
WebVTT with voice tags, SRT with a speaker prefix, or RTTM converted locally
from the diarization alone. A cross-review of the diarization skill led to
shared fixes, each with a test written first:
- the diarization POST waits `max(120, 30 * minutes)` s;
- every service's `run` checks `--output` before any request, so an output
  equal to `--file` or in a missing directory blocks instead of overwriting the
  input or losing a paid answer;
- subtitle speaker labels are flattened, and the 1 ms cue minimum applies after
  rounding;
- `finite()` rejects integers too large for a float;
- `merge` sorts its inputs by time and compares overlaps to the microsecond;
- the 500 MB cap is tested.
`STARTER_RELAY.md` documents the output check, and this service is otherwise
unchanged. The 15 new shared tests failed first, apart from the flag-rule and
cap tests, which only add coverage.
**97 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Second cross-review fixes

Port from neuraldeep-diarization `e376732`. `run` now also blocks an
`--output` that is a directory, and checks the unresolved parent that
`atomic_write()` uses, so a symlink in a read-only directory blocks too.
WebVTT and SRT get one cue per transcript segment, through `label_segments()`.
Huge timestamps and deeply nested input JSON end `blocked`. `merge` parses
input bytes, accepting a UTF-8 byte order mark, and names a file that is not
valid JSON. The new and changed shared tests failed first, apart from the
read-only and missing directory cases, which already passed.
**102 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Third cross-review fixes

Port from neuraldeep-diarization `e4bdae5`. `run` requires read, write and
search permission on the output directory, since `atomic_write()` needs all
three. `merge` decodes strict UTF-8 (a byte order mark is fine), so UTF-16,
UTF-32 and surrogate bytes block; a missing input, an unwritable output and a
lone surrogate escape block with their own messages. `--output` equal to
`--diarization` is tested. The new shared tests failed first, apart from that
coverage case. **104 tests passed** (1 skipped outside a tag build), both
normally and with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`.

## Fourth cross-review fixes

Port from neuraldeep-diarization `336ccf4`. The output check uses
`os.path.isdir()`, because `Path.is_dir()` raises `PermissionError` on Python
3.10 to 3.12 and broke the 3.10 CI job; `run` blocks replacing another user's
file in a sticky directory before any request; the RTTM file ID shows
non-UTF-8 file name bytes as U+FFFD; a tie test has the first speaker last in
alphabetical order. The sticky-directory and file-name tests failed first.
**107 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`, and on Python 3.10.22 (Docker `python:3.10-slim`,
non-root, no network).

## Fifth cross-review fixes

Port from neuraldeep-diarization `49688de`. `run` blocks an output name the
file system refuses (any `lstat` error except `FileNotFoundError`), and the
`run` and `merge` same-file checks add `os.path.samefile()` for hard links and
case aliases. `--format rttm` blocks a lone surrogate speaker label with its own
message, and the diarization artifact is written with ASCII escapes. The new
shared tests failed first. **111 tests passed** (1 skipped outside a tag build),
both normally and with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`, and on Python 3.10.22 (Docker `python:3.10-slim`,
non-root, no network).

## Sixth cross-review fixes

Port from neuraldeep-diarization `5916a17`. An output that is the state file
through a case alias blocks once the state exists, before any request; a new
output name is created with `O_EXCL` and removed before the preflight, so names
vfat, exFAT or SMB refuse on create block early; consecutive unassigned merge
segments stay separate turns. The new shared tests failed first.
**114 tests passed** (1 skipped outside a tag build), both normally and with
`LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`, and on Python 3.10.22 (Docker `python:3.10-slim`,
non-root, no network).

## Seventh cross-review fix

Port from neuraldeep-diarization `c10a179`. Once the state exists, `run`
blocks an input file that is the state file, also through a case alias, before
any request; before, `--file x --state x` with no `x` sent the helper's own
state JSON. The new shared test failed first. **115 tests passed** (1 skipped
outside a tag build), both normally and with `LC_ALL=C PYTHONUTF8=0`, with no
`EncodingWarning` under `-X warn_default_encoding`, and on Python 3.10.22
(Docker `python:3.10-slim`, non-root, no network).

## Eighth cross-review fixes

Port from neuraldeep-diarization `14c0056`. The U+FFFD repair for non-UTF-8
file names applies to the RTTM file ID only, so speaker labels with lone
surrogates block as in the other formats instead of merging; the
input-is-the-state test also covers a dangling symlink. The new RTTM test
failed first. **116 tests passed** (1 skipped outside a tag build), both
normally and with `LC_ALL=C PYTHONUTF8=0`, with no `EncodingWarning` under
`-X warn_default_encoding`, and on Python 3.10.22 (Docker `python:3.10-slim`,
non-root, no network).

## Streamed uploads

Port from neuraldeep-diarization `3b918a7`. `multipart()` returns an
`UploadBody` that `http.client` reads in 64 KB blocks with a normal
`Content-Length`, so the socket timeout bounds each block, not the whole
upload, and no copy of the file is held in memory; exactly the checked size is
sent. The provider documents no chunked or resumable upload, so a broken upload
is never resent. `UPLOAD_LIMITS` keeps only documented limits (diarize
500 MB); this service documents none. The shared multipart tests read the body
with `drain()`. The OCR workflow test reads the upload with `drain()` too. The new shared tests failed first. **120 tests passed**
(1 skipped outside a tag build), both normally and with `LC_ALL=C PYTHONUTF8=0`,
with no `EncodingWarning` under `-X warn_default_encoding`, and on Python
3.10.22 (Docker `python:3.10-slim`, non-root, no network).
