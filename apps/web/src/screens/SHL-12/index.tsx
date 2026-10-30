import type {
  EligibilityCheckOut,
  LadderLevelOut,
  SignOffEligibilityOut,
  SignOffOut,
} from "@abacus/api-client";
import {
  type Actor,
  HumanAction,
  Icon,
  Pill,
  Segmented,
  SheetModal,
  StatusDisc,
  type DiscState,
  Button,
  Tooltip,
  date as formatDate,
  time,
} from "@abacus/ui";
import { type JSX, type ReactNode, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  type SignOffLevel,
  type SignOffTarget,
  levelOf,
  useGate,
  useSignOffEligibility,
  useSignOffLadder,
  useSignOffWrite,
} from "../../domain/review";
import { COPY } from "./copy";

// SHL-12 · Sign-off modal (P-04-T48; P-04 §3 F2; the handoff's SHL-12 folder): the O3 sheet at
// `?ov=signoff:<targetType>:<targetId>[:<level>]`, the only place a sign-off is added (chapter 04
// E7). Frames built here (fixtures/seed/review.ts, P-04-T34 and this task):
//
//   a   Hannah Leclerc signs Trial Balance v1 as Reviewer (L2): the workpaper card with its version
//       and content hash, the level picker limited to the levels the matrix allows, the L1–L5
//       ladder with Marcus Delaney's L1 "performed by Agent run #4127 … adopted by MD", the checks
//       (all pass, the amber G4 warning), the statement, "Sign off as Reviewer (L2)"
//   a′  signed: the sheet closes, the toast "Signed off Trial Balance (L2) · 9:41 AM", the header's
//       "✓ MD ✓ HL" (SignOffChips)
//   b   two open review notes: "Clear 2 open notes to sign off", disabled
//   c   Marcus Delaney on L2 of the workpaper he prepared: segregation, disabled
//   d   no independence confirmation on file (Gate G2): "Confirm independence…", disabled
//   e   changed after Hannah's L2: her chip struck with "Changed after sign-off", View changes,
//       "Re-sign as Reviewer (L2)" (a re-sign is a new row)
//   g   Thomas Whitcombe: the single option "EQR (L5)" and the EQR statement
//   h   Daniel Reyes on the Ridgeline 2025 Form 1065: "Partner · final approval (BH-TAX-02)",
//       11 issues open, "Resolve 11 issues to approve" disabled
//
// Every blocked frame names its reason in words, and the disabled control names the failing check
// as its description. Signing is a HumanAction on the signed-in person (INV-1); the write carries
// the content hash and statement version the person saw and waits for the server (never
// optimistic). Bulk (f) is P-04-T49's.

type LadderLevel = LadderLevelOut["level"];

function isReturn(eligibility: SignOffEligibilityOut): boolean {
  return eligibility.target.target_type === "tax_return";
}

function num(facts: EligibilityCheckOut["facts"], key: string): number | null {
  const v = facts[key];
  return typeof v === "number" ? v : null;
}

function str(facts: EligibilityCheckOut["facts"], key: string): string | null {
  const v = facts[key];
  return typeof v === "string" ? v : null;
}

/** "✓ MD" chips, in level order: struck with the amber pill when stale (e). */
function Initials({ latest }: { latest: SignOffOut }): JSX.Element {
  return latest.stale ? (
    <span className="flex items-center gap-[6px]">
      <span
        data-sign-off-chip={latest.initials}
        data-stale=""
        className="text-meta text-ink-3 line-through"
      >
        ✓ {latest.initials}
      </span>
      <Pill variant="amber" size="sm">
        {COPY.changedAfter}
      </Pill>
    </span>
  ) : (
    <Pill variant="green" size="tally" check data-sign-off-chip={latest.initials}>
      {latest.initials}
    </Pill>
  );
}

/** The header's chips once signed (a′: "✓ MD ✓ HL"), from the ladder read. */
export function SignOffChips({ target }: { target: SignOffTarget }): JSX.Element | null {
  const ladder = useSignOffLadder(target).data;
  if (ladder === undefined) return null;
  const signed = ladder.levels.flatMap((l) => (l.latest === null ? [] : [l.latest]));
  return (
    <span aria-label={COPY.ladder} data-sign-off-chips="" className="flex items-center gap-[4px]">
      {signed.map((s) => (
        <Initials key={s.id} latest={s} />
      ))}
    </span>
  );
}

function PlannedLink({ text, hint }: { text: string; hint: string }): JSX.Element | null {
  if (!PLANNED_VISIBLE) return null;
  return (
    <Tooltip content={hint}>
      <span data-planned-link="" className="text-dense font-medium text-ink">
        {text} <span className="text-ink-3">→</span>
      </span>
    </Tooltip>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-pane bg-card shadow-e1">
      <h3 className="flex h-[33px] items-center border-b-[0.5px] border-hair px-[14px] text-dense font-medium">
        {title}
      </h3>
      {children}
    </section>
  );
}

function LadderRow({
  row,
  current,
  final,
  now,
}: {
  row: LadderLevelOut;
  current: boolean;
  final: boolean;
  now: Date;
}): JSX.Element {
  const latest = row.latest;
  const role = COPY.roles[row.level];
  const label = final
    ? row.level === "L4_partner"
      ? `${role} · ${COPY.finalApproval}`
      : role
    : `${COPY.short[row.level]} ${role}`;
  let disc: DiscState = "todo";
  let detail: string | null = null;
  let sub: string | null = null;
  if (latest !== null && !latest.stale) {
    disc = "done";
    detail = final
      ? latest.signer_name
      : `${latest.signer_name} · ${formatDate(latest.signed_at, { now })}, ${time(latest.signed_at)}`;
    if (latest.adopted_run_number !== null) {
      sub = COPY.performed(latest.adopted_run_number, latest.signer_name, latest.initials);
    }
  } else if (latest !== null && latest.stale) {
    disc = "warn";
    detail = `${latest.signer_name} · ${formatDate(latest.signed_at, { now })}, ${time(latest.signed_at)}`;
  } else if (current) {
    disc = "half";
    detail = COPY.you;
  } else if (!row.required) {
    detail = COPY.optional;
  } else if (row.expected_signer_name !== null) {
    detail =
      row.level === "L5_eqr"
        ? COPY.atCompletion(row.expected_signer_name)
        : COPY.required(row.expected_signer_name);
  }
  return (
    <li
      data-level={row.level}
      {...(current ? { "aria-current": "step" as const } : {})}
      className="flex min-h-[44px] items-center gap-[10px] border-b-[0.5px] border-hair px-[14px] py-[8px] last:border-b-0"
    >
      <StatusDisc state={disc} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-dense">
          <span className="font-medium">{label}</span>
          {detail !== null && <span className="text-ink-3"> · {detail}</span>}
        </span>
        {sub !== null && <span className="text-meta text-ink-3">{sub}</span>}
      </span>
      {latest !== null && <Initials latest={latest} />}
    </li>
  );
}

/** One "Before you sign" row: the disc, the words and what to do. */
function CheckRow({
  check,
  id,
  eligibility,
  now,
}: {
  check: EligibilityCheckOut;
  id: string;
  eligibility: SignOffEligibilityOut;
  now: Date;
}): JSX.Element | null {
  const f = check.facts;
  const fail = check.result === "fail";
  const disc: DiscState = fail ? "fail" : check.result === "warn" ? "warn" : "done";
  let words: string;
  let extra: ReactNode = null;
  let chip: string | null = null;
  switch (check.code) {
    case "open_review_notes": {
      const n = num(f, "count") ?? 0;
      words = fail ? COPY.checksCopy.notesFail(n) : COPY.checksCopy.notesPass(n);
      if (fail) {
        extra = (
          <PlannedLink text={COPY.checksCopy.openNotes} hint={COPY.checksCopy.openNotesHint} />
        );
      }
      break;
    }
    case "independence": {
      const client = str(f, "client") ?? eligibility.target.context_label;
      const on = str(f, "confirmed_on");
      words =
        fail || on === null
          ? COPY.checksCopy.independenceFail(client)
          : COPY.checksCopy.independencePass(
              client,
              str(f, "person") ?? "",
              formatDate(on, { now, withYear: true }),
            );
      if (fail) {
        extra = (
          <PlannedLink
            text={COPY.checksCopy.confirmIndependence}
            hint={COPY.checksCopy.confirmIndependenceHint}
          />
        );
      }
      break;
    }
    case "segregation": {
      const preparer = str(f, "preparer") ?? "";
      const reviewer = str(f, "reviewer");
      words = fail
        ? COPY.checksCopy.segregationFail(COPY.short[eligibility.level])
        : reviewer !== null
          ? COPY.checksCopy.segregationPassReturn(preparer, reviewer)
          : COPY.checksCopy.segregationPass(preparer);
      break;
    }
    case "all_cited": {
      const cited = num(f, "cited") ?? 0;
      const cells = num(f, "cells") ?? 0;
      words = fail
        ? COPY.checksCopy.citedFail(cited, cells)
        : COPY.checksCopy.citedPass(cited, cells);
      break;
    }
    case "gate_g4":
      words = COPY.checksCopy.g4(str(f, "awaiting") ?? "");
      break;
    case "open_issues": {
      words = COPY.checksCopy.issues(
        num(f, "count") ?? 0,
        num(f, "waiting_on_client"),
        num(f, "review_points"),
      );
      chip = str(f, "rule");
      const top = str(f, "top");
      if (fail) {
        extra = (
          <>
            {top !== null && (
              <span className="mt-[6px] flex flex-col rounded-nested bg-card px-[14px] py-[8px] shadow-[inset_0_0_0_0.5px_var(--color-hair)]">
                <span className="text-dense text-ink">{top}</span>
                <span className="text-meta text-ink-3">{COPY.checksCopy.topPoint}</span>
              </span>
            )}
            <PlannedLink text={COPY.checksCopy.openIssues} hint={COPY.checksCopy.openIssuesHint} />
          </>
        );
      }
      break;
    }
    case "eqr_limits":
      words = COPY.checksCopy.eqrLimits;
      break;
  }
  return (
    <li
      id={id}
      data-check={check.code}
      data-result={check.result}
      className="flex min-h-[34px] items-start gap-[10px] border-b-[0.5px] border-hair px-[14px] py-[8px] last:border-b-0"
    >
      <StatusDisc state={disc} className="mt-[1px]" />
      <span className="flex min-w-0 flex-1 flex-col gap-[4px]">
        <span
          className={
            fail
              ? "text-dense text-red-ink"
              : disc === "warn"
                ? "text-dense text-ink-2"
                : "text-dense"
          }
        >
          {words}
        </span>
        {extra}
      </span>
      {chip !== null && (
        <Pill variant="neutral" size="sm">
          {chip}
        </Pill>
      )}
    </li>
  );
}

export interface SignOffSheetProps {
  target: SignOffTarget;
  /** The level asked for, long or short (`?ov=signoff:…:L2`); the server answers the levels the
   * viewer may sign. */
  level?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The header's right ("AUD-06", "2025 Form 1065 · Ridgeline"). */
  meta?: string;
  onSigned?: (signOff: SignOffOut) => void;
}

export function SignOffSheet({
  target,
  level,
  open,
  onOpenChange,
  meta,
  onSigned,
}: SignOffSheetProps): JSX.Element {
  const session = useSession();
  const [asked, setAsked] = useState<SignOffLevel>(levelOf(level) ?? "L1_preparer");
  const query = useSignOffEligibility(target, asked);
  const eligibility = query.data;
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.title}
      {...(meta === undefined
        ? {}
        : { meta: <span className="text-meta text-ink-3">{meta}</span> })}
    >
      {eligibility === undefined ? (
        <p className="p-[12px] text-meta text-ink-3">
          {query.isError ? COPY.missing : COPY.loading}
        </p>
      ) : (
        <Body
          key={`${eligibility.target.content_hash}:${eligibility.level}`}
          target={target}
          eligibility={eligibility}
          actor={actor}
          onLevel={setAsked}
          onCancel={() => {
            onOpenChange(false);
          }}
          onSigned={(s) => {
            onOpenChange(false);
            onSigned?.(s);
          }}
        />
      )}
    </SheetModal>
  );
}

function Body({
  target,
  eligibility,
  actor,
  onLevel,
  onCancel,
  onSigned,
}: {
  target: SignOffTarget;
  eligibility: SignOffEligibilityOut;
  actor: Actor;
  onLevel: (level: SignOffLevel) => void;
  onCancel: () => void;
  onSigned: (signOff: SignOffOut) => void;
}): JSX.Element {
  const now = useNow();
  const ids = useId();
  const ladder = useSignOffLadder(target).data?.levels ?? eligibility.ladder;
  const final = isReturn(eligibility);
  const kind = final ? "final_approval" : "ladder";
  const sign = useSignOffWrite(eligibility);
  const t = eligibility.target;
  const role = COPY.roles[eligibility.level];
  const short = COPY.short[eligibility.level];

  const gate = useGate({
    command: () => sign(kind),
    doneText: (s: SignOffOut) =>
      final
        ? COPY.toasts.approved(t.label, time(s.signed_at))
        : COPY.toasts.signed(t.label, short, time(s.signed_at)),
    failedText: COPY.toasts.failed,
    onDone: onSigned,
  });

  const checkId = (code: string): string => `${ids}-${code}`;
  const failing = eligibility.checks.find((c) => c.result === "fail");
  const notes = eligibility.checks.find(
    (c) => c.code === "open_review_notes" && c.result === "fail",
  );
  const issues = eligibility.checks.find((c) => c.code === "open_issues" && c.result === "fail");
  const mine = ladder.find((l) => l.level === eligibility.level)?.latest ?? null;
  const stale = mine?.stale === true;

  let label: string;
  if (notes !== undefined) label = COPY.cta.clearNotes(num(notes.facts, "count") ?? 0);
  else if (issues !== undefined) label = COPY.cta.resolveIssues(num(issues.facts, "count") ?? 0);
  else if (final) label = COPY.cta.approve;
  else if (stale) label = COPY.cta.reSign(role, short);
  else label = COPY.cta.signOff(role, short);
  const blocked = !eligibility.eligible || failing !== undefined;
  const busy = gate.phase === "busy";

  const rule = final ? (issues === undefined ? null : str(issues.facts, "rule")) : null;
  const options = final
    ? [COPY.finalLevel(rule)]
    : eligibility.levels_allowed.map((l) =>
        l === "L5_eqr" ? `${COPY.roles[l]} (${COPY.short[l]})` : COPY.roles[l],
      );
  const activeOption = final
    ? COPY.finalLevel(rule)
    : eligibility.level === "L5_eqr"
      ? `${role} (${short})`
      : role;
  const eqrOnly =
    !final && eligibility.levels_allowed.length === 1 && eligibility.level === "L5_eqr";

  return (
    <div className="flex flex-col gap-[12px] p-[12px]" data-signoff-target={t.target_type}>
      <div className="flex flex-col gap-[2px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1">
        <span className="flex items-center gap-[8px]">
          <Icon name="file-text" size={16} className="text-ink-2" />
          <span className="text-title font-medium">{t.label}</span>
        </span>
        <span className="text-dense text-ink-3">
          {t.context_label} · {COPY.version(t.version_no)}
        </span>
        <span data-content-hash="" className="font-mono text-meta text-ink-3">
          {[
            COPY.hash(`${t.content_hash.slice(0, 11)}…${t.content_hash.slice(-4)}`),
            ...(t.cell_count > 0 ? [COPY.cells(t.cell_count)] : []),
            ...(t.citation_count > 0 ? [COPY.citations(t.citation_count)] : []),
          ].join(" · ")}
        </span>
      </div>

      <div className="flex flex-col gap-[6px]">
        <Segmented
          label={COPY.levelPicker}
          options={options}
          active={activeOption}
          onChange={(picked) => {
            const next = eligibility.levels_allowed.find(
              (l) => COPY.roles[l] === picked || `${COPY.roles[l]} (${COPY.short[l]})` === picked,
            );
            if (next !== undefined && next !== eligibility.level) onLevel(next);
          }}
        />
        {eqrOnly && <span className="px-[4px] text-dense text-ink-3">{COPY.eqrHelper}</span>}
      </div>

      <Fieldset title={COPY.ladder}>
        <ol>
          {ladder.map((row) => (
            <LadderRow
              key={row.level}
              row={row as LadderLevelOut & { level: LadderLevel }}
              current={row.level === eligibility.level}
              final={final}
              now={now}
            />
          ))}
        </ol>
        {stale && (
          <div className="flex justify-end border-t-[0.5px] border-hair px-[14px] py-[8px]">
            <PlannedLink text={COPY.viewChanges} hint={COPY.viewChangesHint} />
          </div>
        )}
      </Fieldset>

      <Fieldset title={COPY.checks}>
        <ul>
          {eligibility.checks.map((c) => (
            <CheckRow
              key={c.code}
              id={checkId(c.code)}
              check={c}
              eligibility={eligibility}
              now={now}
            />
          ))}
        </ul>
      </Fieldset>

      <p
        aria-label={COPY.statement}
        data-statement={eligibility.statement.version}
        className="rounded-nested bg-card px-[14px] py-[12px] text-dense leading-[1.55] text-ink shadow-e1"
      >
        {eligibility.statement.text}
      </p>

      {gate.blocked !== null && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.blocked[gate.blocked.code] ?? COPY.blocked.fallback}
        </p>
      )}

      <div
        data-signoff="footer"
        className="sticky bottom-0 -mx-[12px] -mb-[12px] flex items-center justify-between gap-[8px] bg-shell px-[12px] py-[12px]"
      >
        <Button variant="secondary" onClick={onCancel}>
          {COPY.cancel}
        </Button>
        <HumanAction
          verb={final ? "Approve" : "Sign off"}
          label={label}
          actor={actor}
          disabled={blocked || busy}
          loading={busy}
          {...(blocked && failing !== undefined
            ? { "aria-describedby": checkId(failing.code) }
            : {})}
          onClick={() => {
            void gate.run();
          }}
        />
      </div>
    </div>
  );
}
