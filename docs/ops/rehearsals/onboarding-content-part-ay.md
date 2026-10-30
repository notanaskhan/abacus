# Onboarding rehearsal, part AY: content through the firm's screens (Q-04-T018)

Staging, on a rehearsal firm that Q-04-T016 (part N) provisioned and took to `LEVEL=shadow` (a real,
non-synthetic tenant holding only synthetic content). The firm's content goes in through its own
screens (`docs/runbooks/pilot-onboarding.md` rule 1); nothing here is loaded by the seed loader or a
commit. Acceptance: every content step completes through its screen with timings recorded, and
each defect has an owning-epic issue.

## Inputs (made for the run, never committed)

    python -m abacus_tools.synthetic.onboarding_files --out <scratch dir> --clients 200 \
        --near "<one client the rehearsal firm already holds>"

`clients-200.csv` (CCH Axcess Tax headings, ` (Synthetic)` names, `example.test` mail, no TIN column)
and `pbc-template.xlsx` (KNW-01 Workbook v2). Record `manifest.json`'s SHA-256s below so the run is
reproducible.

## Steps and timings

Time each step from its first click to the screen state named. A step that cannot complete is a
defect: file it on the owning epic and write its issue in the row.

| # | Step | Screen and state | Who | Started | Done | Minutes | Result | Defect (issue, epic) |
|---|---|---|---|---|---|---|---|---|
| 1 | Upload `clients-200.csv` | CLI-06 import, `reviewing` with `counts.rows` 201 | firm admin | | | | | |
| 2 | Decide every row that waits (the `--near` row and any dedupe hit) | CLI-06 review, `counts.to_review` 0 | firm admin | | | | | |
| 3 | Run the import | CLI-06 **g** (done: `imported`, `new`, `skipped`, `failed`) | firm admin | | | | | |
| 4 | Import `pbc-template.xlsx` | KNW-01 importer, version `needs_review` (lifecycle on) or published | quality partner | | | | | |
| 5 | Approve the imported template version | KNW-01, version Published ("Approved") | quality partner | | | | | |
| 6 | Edit and publish the firm's email templates | POR-20 **l** (published) | firm admin | | | | | |
| 7 | Add the firm's sender domain | ADM-10 **d** (pending DNS) | firm admin | | | | | |
| 8 | Publish the DNS records, wait for verification | ADM-10 **e** to **f** (verified, published) | firm admin and N | | | | | |

Inputs used: `clients-200.csv` sha256 `—` · `pbc-template.xlsx` sha256 `—` · seed `2027` · staging
SHA `—`.

## Runs

| Date | Staging SHA | Operator | Total minutes | Steps green | Defects filed | Notes |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | not run yet: needs part N's rehearsal firm on staging (Q-04-T016) and ADM-10's live sender domains (R-01-T27) |

After each run copy the per-section minutes into `docs/runbooks/pilot-onboarding.md` § Timings
(sections 4 to 7) and file each defect with the **owning epic** in the issue title and body.
