---
id: TASK-328
title: "F-05-T12: status.ts runtime over the C2 data, the C-06 Status kit components and the RETIRED map for the 144 status.js words"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-14]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T12
branch: task-326-status-kit
worktree: agent-aff82f8f1692b1936
created: 2026-10-21
updated: 2026-10-21
---

## Plan
The plan's acceptance for F-05-T12 (epic F-05 §3.B2): every blueprint 3.3.1 and addendum 3.2 row resolves, every status.js word is mapped or retired, and an OpenAPI enum literal without an entry fails tsc. SPEC-048 AC-3 (axe finds nothing serious on `/components`) and AC-14 (pills take `--radius-pill`) apply to the specimens.

- **Generator** (`abacus_tools.codegen.status_vocabulary`, then `make regenerate`): `status.gen.ts` also carries `HANDOFF_WORDS` (each of the 144 words is a registry code or retired with its reason and replacement), `RETIRED_CODES`, and the registry fields it dropped (`contextVariants`, `textTone`, `emphasis`). The generator refuses a word that has no home, or a count other than 21 objects and 144 words.
- **Runtime** (`packages/ui/src/status.ts`, was `status.tsx`): `status(object, code, {context, client, vars})` returns the word, the kit variant, size, disc, glyph, check and tone. `registryWord`, `statusWord`, `STATUS` stay for current callers. `RETIRED`, `handoffStatus` and `HANDOFF_OBJECTS` answer for the 144 words.
- **Components** (`components/status.tsx`): `StatusPill`, `StatusDisc`, `SubLine`, `SyncChip`, `Tick`, `TallyPill`, and `RegistryStatus` (a registry state as the kit draws it). `Status` and the old `StatusPill` props (`tone`) keep working.
- **tsc check**: `EnumCovered<Object, Enum>` in the runtime; `apps/web/src/status/enums.ts` assigns `true` to it for `EngagementStatus`, `RequestStatus` and `AuditSectionStatus`.
- **Specimens**: seven in the `/components` gallery (C-06: pills, discs, sub-lines, sync chip, ticks, tally pills, and the status map of every word).
- No migration, no new dependency. Rollback is a revert.

## Notes
- DEC-124: pills are `rounded-pill` (999). DEC-123 ("keep the 7px squares") is superseded and not followed.
- Conflicts between the bundle, `kits.md`, the blueprint and the repo are one line each in `packages/ui/src/tokens/DECISIONS.md`, "Status kit".
- The YAML's `handoff_words` were checked against both copies of `lib/status.js` (the C-06 bundle and `sources/handoff/lib/status.js`): the same 21 objects, 144 words and order. 123 are mapped; 21 are retired (two have a registry replacement: `Engagement.Draft` to `engagement.prospect`, `Issue.Waiting on client` to `card_overlay.waiting_on_client`).
- `ui.*` entries in the YAML's `retired` block were "inferred; F-05-T12 to confirm". The test confirms each names a real legacy `STATUS` code and a registry replacement that exists.
- `packages/ui` has no test script: its tests live in `apps/web/src` (the status ones in `apps/web/src/status/`).

## Definition of done
- [x] `status.test.ts`: all 56 objects and 290 codes resolve, contexts and client wording hold, the 144 words are 123 mapped and 21 retired.
- [x] `enums.test.ts`: two `@ts-expect-error` lines prove an enum literal with no entry, and a stored code the enum lacks, fail tsc.
- [x] `statusKit.test.tsx`: variants, sizes, discs, sub-line, sync chip, ticks, tally and `RegistryStatus` (62 tests across the three files).
- [x] Backend: `test_status_vocabulary.py` (13), including the handoff map and the retired codes.
- [x] apps/web tests (667) pass.
- [x] Axe on the `/components` page (injected into the running gallery) finds no serious or critical violations.
- [x] check-fast passes.

## Progress log
- `2026-10-21` Built the generator change, runtime, components, specimens and tests. Checked the specimens in the browser against the bundle's screenshots 01, 03 and 04 (discs, ticks, sync chip). Pill spacing is `px-[8px]` because the root font size is 14px and `px-2` came out as 7px.
- `2026-10-21` Gotcha, first time: `cn()` (tailwind-merge) read `text-pill` as a colour and dropped `text-amber-ink` from the same class list; the kit joins classes with `clsx` and the finding is in DECISIONS.md. Teach `cn` the type roles before F-05-T14 relies on it.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Words, variants and discs from the registry; the bundle only for drawing | DEC-08: one source of truth; status.js was drafted | no |
| `soon` and `muted` ink on the AA ladder | DEC-11; the bundle's `ink-4` fails axe | no |
| Registry discs C-06 does not draw resolve to no disc, with the name kept in `mark` | The owning kit draws them | no |
| Tick is built here, not in F-05-T14 | F-05-T12's row names it | no |

## Gotchas and discoveries
- A registry state with `variant: null` is a disc and an 11.5px line, not a pill; the bundle drew a few of these (Agent run "Running", Issue "Open") as pills.
- `Status` is the legacy `{domain, value}` component, so the bundle's `<Status object word>` is `RegistryStatus`.

## Handoff
Done. F-05-T14 builds Button, Pill, Count, Tag, DoneCount and CheckPill on the pill token and can reuse the sizes in `components/status.tsx` (count, done, check and chip are already in its size table).
