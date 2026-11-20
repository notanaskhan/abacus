// ENG-07 · Season setup / roll-forward (T-08-T15; docs/screens/ENG-07.md; T-08 §3; SPEC-710 AC-1 to
// AC-5): T6. Subbar with the provenance chip (the planner drafted) and View run ›; the control bar
// (Cohorts · All clients · Exceptions); the tally strip (214 · 224 · 241 · 4 of 6 · 126 of 214 ·
// 3); the manifest with cohort GroupBands and their rows, office filter and search; row
// selection, Reassign and Exclude; the sticky approval bar with its confirm Dialog and Withdraw;
// executing progress; the ask card (or, planner off, the code exception row). Every count is the
// server's; Approve is absent for anyone the cohort does not allow (Grace Holloway).
import type {
  SeasonAskOut,
  SeasonCohortOut,
  SeasonManifestOut,
  SeasonManifestRowOut,
} from "@abacus/api-client";
import { Button, Dialog, Pill, Segmented, type TallyItem, TallyStrip } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export type Eng07View = "cohorts" | "all" | "exceptions";

const day = (iso: string): string =>
  new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "America/Chicago",
  });
const at = (iso: string): string =>
  new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Chicago",
  });

export function tallyItems(m: SeasonManifestOut): TallyItem[] {
  return [
    { label: COPY.tally.engagements, value: m.tally.engagements.toLocaleString("en-US") },
    { label: COPY.tally.returns, value: m.tally.returns.toLocaleString("en-US") },
    { label: COPY.tally.binders, value: m.tally.binders.toLocaleString("en-US") },
    { label: COPY.tally.approved, value: COPY.of(m.tally.cohorts_approved, m.tally.cohorts) },
    {
      label: COPY.tally.created,
      value: m.tally.created.toLocaleString("en-US"),
      info: `of ${String(m.tally.engagements)}`,
    },
    {
      label: COPY.tally.exceptions,
      value: String(m.tally.exceptions),
      ...(m.tally.exceptions ? { pill: { text: COPY.check, variant: "amber" as const } } : {}),
    },
  ];
}

function CohortPill({ c }: { c: SeasonCohortOut }): JSX.Element {
  if (c.display === "executed" && c.approved_at)
    return <Pill variant="green">{COPY.executedOn(day(c.approved_at))}</Pill>;
  if (c.display === "executing")
    return <Pill variant="neutral">{COPY.executingOf(c.created_rows ?? 0, c.engagements)}</Pill>;
  if (c.display === "queued" && c.queued_after != null && c.approver && c.approved_at)
    return <Pill variant="green">{COPY.approvedBy(c.approver.name, at(c.approved_at))}</Pill>;
  if (c.display === "queued") return <Pill variant="green">{COPY.display.queued}</Pill>;
  if (c.display === "review_required")
    return (
      <span className="inline-flex gap-[4px]">
        <Pill variant="neutral">{COPY.display.draft}</Pill>
        <Pill variant="amber">{COPY.display.review_required}</Pill>
      </span>
    );
  return <Pill variant="neutral">{COPY.display[c.display]}</Pill>;
}

export interface ENG07Props {
  manifest: SeasonManifestOut;
  rows: SeasonManifestRowOut[];
  view: Eng07View;
  onView?: (v: Eng07View) => void;
  expanded?: number;
  onApprove?: (cohortId: string) => void;
  onWithdraw?: (cohortId: string) => void;
  onAnswer?: (ask: SeasonAskOut, option: string) => void;
  onReassign?: (rowId: string) => void;
  onExclude?: (rowIds: string[]) => void;
  onViewRun?: () => void;
  initialConfirm?: boolean;
}

export function ENG07({
  manifest: m,
  rows,
  view,
  onView,
  expanded = 5,
  onApprove,
  onWithdraw,
  onAnswer,
  onReassign,
  onExclude,
  onViewRun,
  initialConfirm = false,
}: ENG07Props): JSX.Element {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [confirm, setConfirm] = useState(initialConfirm);
  const [askDone, setAskDone] = useState(false);
  const open = m.cohorts.find((c) => c.position === expanded);
  const executing = m.cohorts.find((c) => c.display === "executing");
  const shown = rows.filter(
    (r) =>
      (view !== "exceptions" || (r.exception_codes ?? []).length > 0) &&
      (q === "" || r.client_name.toLowerCase().includes(q.toLowerCase())),
  );
  const ask = (m.asks ?? [])[0];
  const labels: Record<Eng07View, string> = {
    cohorts: COPY.segments.cohorts,
    all: COPY.segments.all,
    exceptions: `${COPY.segments.exceptions} ${String(m.tally.exceptions)}`,
  };
  return (
    <div data-screen="ENG-07" className="relative flex min-h-0 flex-1 flex-col">
      <div className="flex h-[42px] items-center gap-[8px] px-[12px]">
        <span className="text-[14px] text-ink-2">{COPY.back}</span>
        <span className="flex-1 text-center text-[15px] font-medium text-ink">
          {COPY.title} <span className="font-normal text-ink-2">{COPY.context}</span>{" "}
          <Pill variant="neutral">{COPY.inProgress}</Pill>
        </span>
        <span
          data-provenance=""
          className="rounded-[8px] bg-nested px-[8px] py-[4px] text-[12.5px] text-ink-2"
        >
          {COPY.provenance}
        </span>
        <Button variant="secondary" size="sm" onClick={onViewRun}>
          {COPY.viewRun}
        </Button>
      </div>
      <div className="flex h-[44px] items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.manifest}
          options={[labels.cohorts, labels.all, labels.exceptions]}
          active={labels[view]}
          {...(onView === undefined
            ? {}
            : {
                onChange: (l: string) => {
                  onView(
                    (Object.keys(labels) as Eng07View[]).find((k) => labels[k] === l) ?? "cohorts",
                  );
                },
              })}
        />
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">
          {COPY.manifest}
        </span>
        <Button variant="ghost" size="sm">
          {COPY.export}
        </Button>
      </div>
      <TallyStrip label={COPY.manifest} items={tallyItems(m)} className="px-[12px] pb-[10px]" />
      <section
        aria-label={COPY.cohortsTitle}
        className="mx-[12px] flex min-h-0 flex-1 flex-col rounded-card bg-card shadow-e1"
      >
        <div className="flex h-[46px] items-center gap-[8px] px-[12px]">
          <input
            aria-label={COPY.search}
            placeholder={COPY.search}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-[30px] w-[200px] rounded-[8px] bg-nested px-[8px] text-body"
          />
          <h2 className="flex-1 text-center text-[13.5px] font-medium text-ink">
            {COPY.cohortsTitle}
          </h2>
          <Button variant="ghost" size="sm">
            {COPY.office}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          <table aria-label={COPY.manifest} className="w-full text-body">
            <thead>
              <tr className="h-[30px] bg-nested text-left text-dense text-ink-2">
                {COPY.columns.map((c) => (
                  <th key={c} className="px-[8px] font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {m.cohorts.map((c) => (
                <CohortBand
                  key={c.cohort_id}
                  c={c}
                  expanded={c.position === expanded}
                  rows={c.position === expanded ? shown : []}
                  selected={selected}
                  onToggle={(id) => {
                    const next = new Set(selected);
                    if (next.has(id)) next.delete(id);
                    else next.add(id);
                    setSelected(next);
                  }}
                  view={view}
                  onReassign={onReassign}
                  onExclude={onExclude}
                />
              ))}
              <tr className="h-[34px] border-t border-ink-3 font-medium">
                <td className="px-[8px]">{COPY.totals}</td>
                <td className="px-[8px] tabular-nums">
                  {`${String(m.tally.engagements)} · ${String(m.tally.returns)} · ${String(m.tally.binders)}`}
                </td>
                <td colSpan={8} />
              </tr>
            </tbody>
          </table>
          {open ? (
            <p className="px-[12px] py-[6px] text-[12.5px] text-ink-3">
              {COPY.showing(rows.length, open.engagements, open.position, open.exceptions)}
            </p>
          ) : null}
        </div>
        {!m.planner_available ? (
          <p
            role="status"
            data-code-exception=""
            className="mx-[12px] mb-[6px] text-[12.5px] text-amber-ink"
          >
            {COPY.plannerOff}
          </p>
        ) : ask && !askDone && ask.answered_option == null ? (
          <div
            role="group"
            aria-label={COPY.ask.title}
            data-ask=""
            className="mx-[12px] mb-[6px] rounded-[12px] bg-card p-[10px] shadow-e2"
          >
            <p className="text-body text-ink">{COPY.ask.title}</p>
            <div className="mt-[6px] flex gap-[6px]">
              {ask.options.map((o) => (
                <Button
                  key={o.code}
                  variant={o.code === ask.recommended_option ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => {
                    onAnswer?.(ask, o.code);
                    setAskDone(true);
                  }}
                >
                  {o.label}
                </Button>
              ))}
              <Button variant="ghost" size="sm" onClick={() => setAskDone(true)}>
                {COPY.ask.skip}
              </Button>
            </div>
          </div>
        ) : null}
        {open ? (
          <div
            data-approval-bar=""
            className="flex h-[56px] flex-none items-center gap-[10px] border-t border-hair px-[14px]"
          >
            <span className="text-[13.5px] font-medium text-ink">
              {COPY.bar.title(open.position, open.office_name, COPY.segment[open.segment])}
            </span>
            <span className="flex-1 text-[12.5px] text-ink-2">
              {open.queued_after != null
                ? COPY.queuedAfter(open.queued_after)
                : COPY.bar.counts(
                    open.engagements,
                    open.returns,
                    open.binders,
                    open.letters,
                    open.invitations,
                  )}
            </span>
            {(open.allowed_actions ?? []).includes("exclude") ? (
              <Button
                variant="ghost"
                size="sm"
                disabled={selected.size === 0}
                onClick={() => onExclude?.([...selected])}
              >
                {COPY.bar.exclude}
              </Button>
            ) : null}
            {(open.allowed_actions ?? []).includes("reassign") ? (
              <Button variant="secondary" size="sm">
                {COPY.bar.edit}
              </Button>
            ) : null}
            {(open.allowed_actions ?? []).includes("approve") ? (
              <span className="flex flex-col items-end">
                <Button variant="primary" opensDialog onClick={() => setConfirm(true)}>
                  {COPY.bar.approve(open.position)}
                </Button>
                <span className="text-[11.5px] text-ink-3">{COPY.bar.helper}</span>
              </span>
            ) : null}
            {(open.allowed_actions ?? []).includes("withdraw") ? (
              <Button variant="secondary" size="sm" onClick={() => onWithdraw?.(open.cohort_id)}>
                {COPY.bar.withdraw}
              </Button>
            ) : null}
          </div>
        ) : null}
      </section>
      {executing?.approver ? (
        <p
          role="status"
          data-running=""
          className="pointer-events-none absolute bottom-[70px] left-1/2 -translate-x-1/2 rounded-full bg-card px-[14px] py-[10px] text-body shadow-e2"
        >
          {COPY.running(executing.position, executing.approver.name)}
        </p>
      ) : null}
      {open ? (
        <Dialog
          open={confirm}
          onOpenChange={setConfirm}
          title={COPY.bar.confirm(open.engagements, open.office_name)}
          description={COPY.bar.helper}
        >
          <div className="flex justify-end p-[12px]">
            <Button
              variant="primary"
              onClick={() => {
                onApprove?.(open.cohort_id);
                setConfirm(false);
              }}
            >
              {COPY.bar.approve(open.position)}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

function CohortBand({
  c,
  expanded,
  rows,
  selected,
  onToggle,
  view,
  onReassign,
  onExclude,
}: {
  c: SeasonCohortOut;
  expanded: boolean;
  rows: SeasonManifestRowOut[];
  selected: ReadonlySet<string>;
  onToggle: (id: string) => void;
  view: Eng07View;
  onReassign?: ((id: string) => void) | undefined;
  onExclude?: ((ids: string[]) => void) | undefined;
}): JSX.Element {
  return (
    <>
      <tr
        data-cohort={c.position}
        className={`h-[44px] border-t border-hair ${expanded ? "bg-selected" : "bg-nested"}`}
      >
        <td className="px-[8px] text-[13.5px] font-medium text-ink">
          {`C${String(c.position)} ${c.office_name} · ${COPY.segment[c.segment]}`}
        </td>
        <td className="px-[8px] text-right tabular-nums">
          {`${String(c.engagements)} · ${String(c.returns)} · ${String(c.binders)}`}
        </td>
        <td colSpan={2} />
        <td className="px-[8px]">{c.approver?.initials ?? ""}</td>
        <td colSpan={4} />
        <td className="px-[8px]">
          <CohortPill c={c} />
        </td>
      </tr>
      {rows.map((r) => (
        <tr
          key={r.row_id}
          data-row={r.row_id}
          data-display={r.display}
          className="h-[40px] border-t border-hair text-[13px]"
        >
          <td className="px-[8px] pl-[25px]">
            <label className="flex items-start gap-[6px]">
              <input
                type="checkbox"
                aria-label={r.client_name}
                checked={selected.has(r.row_id)}
                onChange={() => onToggle(r.row_id)}
              />
              <span>
                <span className="block text-ink">{r.client_name}</span>
                {r.sub_line ? (
                  <span
                    className={`block text-[11.5px] ${(r.exception_codes ?? []).length ? "text-amber-ink" : "text-ink-3"}`}
                  >
                    {r.sub_line}
                  </span>
                ) : null}
              </span>
            </label>
          </td>
          <td className="px-[8px]">{r.forms.join(", ")}</td>
          <td className="px-[8px]">{r.preparer?.initials ?? ""}</td>
          <td className="px-[8px]">{r.reviewer?.initials ?? ""}</td>
          <td className="px-[8px]">{r.signer?.initials ?? ""}</td>
          <td className="px-[8px]">{r.binder_summary}</td>
          <td className="px-[8px]">
            {COPY.renewal(r.fee_change_pct ? String(Number(r.fee_change_pct)) : null)}
          </td>
          <td className="px-[8px]">{COPY.consents(r.consent_purposes.length, r.signers)}</td>
          <td className="px-[8px]">{r.invitees.join(" · ")}</td>
          <td className="px-[8px]">
            {view === "exceptions" && (r.exception_codes ?? []).length ? (
              <span className="flex gap-[4px]">
                <Button variant="secondary" size="sm" onClick={() => onReassign?.(r.row_id)}>
                  {COPY.reassign}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => onExclude?.([r.row_id])}>
                  {COPY.excludeRow}
                </Button>
              </span>
            ) : r.display === "check" ? (
              <Pill variant="amber">{COPY.check}</Pill>
            ) : r.display === "created" ? (
              <Pill variant="green">{COPY.created}</Pill>
            ) : (
              <Pill variant="neutral">{COPY.ready}</Pill>
            )}
          </td>
        </tr>
      ))}
    </>
  );
}
