---
id: TASK-2204
title: P-11-T02 renderer toolchain and byte-stability spike
spec: SPEC-520
acceptance_criteria: [AC-30, AC-6, AC-20]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T02
branch: s17-p11-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Prove WeasyPrint and python-docx render a three-page letter byte-identically across two fresh
containers and in CI, with the dependencies allowlisted (DEC-16), a digest-pinned worker-batch
image (pinned Pango, HarfBuzz, fontconfig), vendored fonts with licences and a manifest, and a
golden harness in `backend/tests/golden/render/`; or record the Typst fallback.

Acceptance: "A three-page letter fixture renders byte-identical PDF and DOCX in two fresh
containers and in CI, or you record the Typst fallback."

## Plan (red: written before building)
Files:
- `docs/architecture/dependency-allowlist.yaml` (protected): `weasyprint`, `python-docx`,
  `pillow-heif` runtime (DEC-16 batch).
- `backend/pyproject.toml`, `backend/uv.lock`: the three dependencies, pinned.
- `deploy/worker-batch/Dockerfile` (new or extended): base image by digest; `apt` pins for
  `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b`, `fontconfig`; `FONTCONFIG_FILE` pointing
  at `reporting/fonts/fonts.conf`; no other fonts installed.
- `backend/src/abacus/modules/reporting/fonts/`: Arimo, Gelasio (OFL 1.1) and Geist Mono (OFL 1.1)
  TTFs from `@fontsource`'s upstream sources with their licence files, `fonts.conf` listing only
  this directory, `MANIFEST.sha256`.
- `backend/src/abacus/modules/reporting/render/` (spike scope): `fetcher.py` (deny-all URL
  fetcher), `pdf.py` (WeasyPrint with fixed metadata and identifier), `docx.py` (python-docx with
  fixed core properties, ZIP rebuilt sorted with a fixed timestamp, as `evidence/render.py`).
- `backend/tests/golden/render/`: `letter_fixture.py` (a synthetic three-page letter, Brightwater
  Hale wording from the synthetic scenario), `test_ac30_byte_stability.py` (render twice in
  process and compare SHA-256; compare to the committed golden), `letter.pdf.sha256`,
  `letter.docx.sha256`, and `two_containers.sh` (build the image, render in two fresh containers,
  compare).
- CI: a job step running `two_containers.sh` on the worker image (ci.yml), behind the golden
  harness marker.
Migrations, registry, flags: none. Rollback: revert; nothing imports the renderer yet.
Risks: Pango/HarfBuzz versions on the host differ from the image: goldens are only meaningful in
the image, so the in-process test compares two runs and the committed hash is checked in the image.

## Progress log
- `2026-10-29` — Planned in P-11-T01.
- `2026-10-29` — Built on `s17-p11-t02` (build-only): allowlist and lock (WeasyPrint 70.0, pydyf
  0.13.0, python-docx 1.2.0, pillow-heif 1.8.1); Dockerfile pins the base's Pango 1.56.3-1,
  HarfBuzz 10.2.0-1+deb13u1, fontconfig 2.15.0-2.3 in the test and runtime stages with
  `FONTCONFIG_FILE`; vendored WOFF faces from the pinned @fontsource 5.3.0 packages (Arimo 400/700,
  Gelasio 400/500/700, Geist Mono 400/500) with OFL licences and `MANIFEST.sha256`; `render/`
  (assets checked against the manifest, deny-all `asset:` fetcher, PDF with dates from `as_of`
  and the identifier from the content hash, DOCX with fixed properties and a rebuilt ZIP); the
  synthetic golden letter; `tests/golden_render/` (render script, image-bound suite,
  `two_containers.sh`); `make golden-render`; the CI job `render-golden` in the stage-2 gate.
  The goldens are recorded at the S17 end review's first green two-container run
  (`RECORD_GOLDEN=1`).
- `2026-10-30` — End review. **Spike finding:** WOFF faces through `@font-face` left fontconfig
  with no fonts and Pango crashed (exit 139). Fixed by vendoring TrueType faces converted with
  fontTools from the same @fontsource 5.3.0 WOFF files, listed by `fonts.conf`
  (`<dir prefix="relative">.</dir>`, no system directory). **Result:** `make golden-render` renders
  the three-page letter byte-identically in two fresh `--network none` containers: PDF
  `283cbed1…`, DOCX `b1c8f354…`; recorded in `tests/golden_render/letter.*.sha256`; the in-image
  suite passes 8/8 (dates from `as_of`, URL refusals incl. the metadata address, `file:`, `data:`,
  unknown asset). AC-30 met in two containers; the CI half runs with the `render-golden` job.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| WOFF faces from the @fontsource packages already locked for the web app | same font binaries as the UI's, licences included, no download | no |
| The golden suite lives in `tests/golden_render/`, run only in the image (`make golden-render`, CI job) | WeasyPrint's native libraries exist only in the pinned image; a host run would test the wrong Pango | no |
| TrueType through fontconfig, not WOFF through @font-face | fontconfig cannot read WOFF and Pango crashes with no font | no |
| apt pins equal the digest-pinned base's candidates | the weekly base refresh moves them together with a re-baseline (ADR-320 §8) | no |
