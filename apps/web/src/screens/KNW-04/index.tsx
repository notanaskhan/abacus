import type {
  StandardDetailOut,
  StandardExampleRowOut,
  StandardExamplesOut,
  StandardOut,
  StandardVersionOut,
  StandardVersionSummaryOut,
} from "@abacus/api-client";
import {
  listStandardsOptions,
  standardExamplesOptions,
  standardOptions,
} from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  ErrorState,
  Fieldset,
  FlagOffState,
  Pill,
  SettingsLayout,
  Skeleton,
  StatusDisc,
  Timeline,
  Toggle,
  amount,
  cn,
  date,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { COPY, SECTIONS, type Section } from "./copy";
import { DEADLINE_COPY } from "./deadline-copy";
import { DeadlineRulesSection } from "./deadline-rules";
import { DRAFT_PILL, DraftPane, useNewVersion } from "./draft";

export type { Section } from "./copy";

// KNW-04 · Firm standards & thresholds, read states a–h (K-02-T13; docs/screens/KNW-04.md; SPEC-500
// AC-13, AC-14). T12 SettingsLayout: the "Standards" section list beside the form pane, whose
// header carries the version chip (or BH-TAX-02's code), the green-tint "Published … · owner"
// pill, New version… and Apply to returns… (enabled on Review checklists only); fieldsets of rows
// below, then the examples the registered providers give (the designed empty state when none is
// registered) and, on AJE thresholds, the Versions timeline.
//
// K-02-T14 (state i): the standard's owner with an open draft sees the draft pane (`draft.tsx`)
// with its Save bar; New version… opens one from the version in effect (one draft at a time). The
// examples stay on the published read view (KNW-04 deviation D7). The policy toggles are display-only (DEC-53: the
// policy principal is dormant) and link ADM-04. Every number comes from the C21 reads; nothing is
// computed but the AJE example totals, which foot the provider's rows. No control lets the Accrued
// Agent approve, publish or decide.

/** The standards sections plus j, Deadline rules (K-02-T17; DF-10), which reads the platform
 * reference sets rather than a firm standard and carries no edit control. */
export type KnwSection = Section | "deadline_rules";
const DEADLINE = "deadline_rules" as const;

export interface Knw04Initial {
  /** A section id (`?section=`); an unknown one opens AJE thresholds. */
  section?: string;
  /** The checklist selected on Review checklists (its key). */
  checklist?: string;
}

export interface Knw04Props {
  initial?: Knw04Initial;
  onBack?: () => void;
  onSection?: (section: KnwSection) => void;
  /** K-02-T14: New version… opens the draft. */
  onNewVersion?: (standardId: string) => void;
}

const DEFAULT_SECTION: Section = "aje_thresholds";
const PERIOD = "2026-08";

type Payload = StandardVersionOut["payload"];
type Of<K extends Payload["kind"]> = Extract<Payload, { kind: K }>;

const whole = (v: number): string => amount(String(v), "whole").text;
const dollars = (v: number): string => `$${whole(v)}`;
const percent = (v: string): string => `${v}%`;

/** A fieldset table: the #EFEEEB sub-header row and rows on hairlines (no DataTable; T12). */
function Grid({
  head,
  cols,
  rows,
  footer,
  right = [],
  label,
}: {
  head: readonly string[];
  cols: string;
  rows: readonly {
    key: string;
    cells: readonly ReactNode[];
    selected?: boolean;
    muted?: boolean;
  }[];
  footer?: ReactNode;
  right?: readonly number[];
  label: string;
}): JSX.Element {
  // The footer (a total, a helper) sits after the table: a table holds only rows (axe).
  return (
    <>
      <div role="table" aria-label={label}>
        <div
          role="row"
          className="grid min-h-[30px] items-center gap-[12px] border-b-[0.5px] border-hair bg-nested px-[12px] text-th text-ink-2"
          style={{ gridTemplateColumns: cols }}
        >
          {head.map((h, i) => (
            <span key={h} role="columnheader" className={cn(right.includes(i) && "text-right")}>
              {h}
            </span>
          ))}
        </div>
        {rows.map((r) => (
          <div
            key={r.key}
            role="row"
            aria-selected={r.selected === true ? true : undefined}
            className={cn(
              "grid min-h-[34px] items-center gap-[12px] border-b-[0.5px] border-hair px-[12px] py-[6px] text-body",
              r.selected === true && "bg-sel-bg",
              r.muted === true && "text-ink-2",
            )}
            style={{ gridTemplateColumns: cols }}
          >
            {r.cells.map((c, i) => (
              <span
                key={i}
                role="cell"
                className={cn("min-w-0", right.includes(i) && "text-right tabular-nums")}
              >
                {c}
              </span>
            ))}
          </div>
        ))}
      </div>
      {footer}
    </>
  );
}

function Helper({ children }: { children: ReactNode }): JSX.Element {
  return <p className="px-[12px] py-[8px] text-meta text-ink-3">{children}</p>;
}

function Meta({ children }: { children: ReactNode }): JSX.Element {
  return <span className="text-meta text-ink-3">{children}</span>;
}

function Planned({ label, hint }: { label: string; hint: string }): JSX.Element | null {
  if (!PLANNED_VISIBLE) return null;
  return (
    <span aria-disabled="true" title={hint} className="text-dense font-medium text-ink-3">
      {label} <span aria-hidden="true">›</span>
    </span>
  );
}

/** A display-only switch (DEC-53, ADR-149): never interactive, described by where it lives. */
function DisplayToggle({ label, helper }: { label: string; helper: string }): JSX.Element {
  const id = `knw04-${label.length.toString(36)}-help`;
  return (
    <div className="flex items-start justify-between gap-[16px] px-[12px] py-[10px]">
      <div className="flex min-w-0 flex-col gap-[4px]">
        <span className="text-body">{label}</span>
        <span id={id} className="text-meta text-ink-3">
          {helper}
        </span>
      </div>
      <span aria-describedby={id}>
        <Toggle label={label} checked={false} disabled />
      </span>
    </div>
  );
}

function ExampleLine({ row }: { row: StandardExampleRowOut }): JSX.Element {
  return (
    <div className="flex items-center gap-[8px] px-[12px] py-[9px] text-body">
      <StatusDisc state="warn" />
      <span>
        {row.label}
        {row.detail === null ? null : ` — ${row.detail}`}
      </span>
    </div>
  );
}

function ExamplesEmpty(): JSX.Element {
  return (
    <EmptyState icon="list-checks" title={COPY.examplesEmpty}>
      {COPY.examplesEmptyBody}
    </EmptyState>
  );
}

// --- a · AJE thresholds -------------------------------------------------------------------------

function AjeSection({
  payload,
  title,
  owner,
  version,
  examples,
  timeline,
}: {
  payload: Of<"aje_thresholds">;
  title: string;
  owner: string;
  version: number;
  examples: StandardExamplesOut | undefined;
  timeline: ReactNode;
}): JSX.Element {
  const c = COPY.aje;
  const rows = payload.rows.map((r) => ({
    key: r.account_class,
    cells: [
      r.account_class,
      r.rule === "limit" && r.limit_usd !== null ? (
        dollars(r.limit_usd)
      ) : r.rule === "review_required" ? (
        <span className="text-amber-ink">{c.reviewRequired}</span>
      ) : (
        <span className="font-medium">{c.alwaysHeld}</span>
      ),
      `${c.approver[r.approver_level]}${r.batch ? c.batch : ""}`,
    ],
  }));
  const ex = examples?.provider_registered === true ? examples.rows : [];
  const within = ex.filter((r) => r.outcome === "within_threshold");
  const held = ex.filter((r) => r.outcome === "review_required");
  const sum = (rs: StandardExampleRowOut[]) =>
    whole(rs.reduce((t, r) => t + (r.amount_usd ?? 0), 0));
  return (
    <>
      <Fieldset flush title={title} action={<Meta>{COPY.owner(owner)}</Meta>}>
        <Grid
          label={title}
          head={c.head}
          cols="minmax(0,1.4fr) minmax(0,1fr) minmax(0,1.1fr)"
          rows={rows}
          footer={<Helper>{c.helper}</Helper>}
        />
      </Fieldset>
      <Fieldset flush title={c.policyTitle}>
        <DisplayToggle label={c.policyToggle(title)} helper={c.policyHelper} />
        <div className="px-[12px] pb-[8px]">
          <Planned label={c.policyTitle} hint={COPY.plannedAdm04} />
        </div>
      </Fieldset>
      <Fieldset
        flush
        title={c.examplesTitle(version)}
        action={examples?.caption == null ? undefined : <Meta>{examples.caption}</Meta>}
      >
        {ex.length === 0 ? (
          <ExamplesEmpty />
        ) : (
          <Grid
            label={c.examplesTitle(version)}
            head={c.examplesHead}
            cols="minmax(0,1.4fr) 90px minmax(0,1.5fr)"
            right={[1]}
            rows={ex.map((r) => ({
              key: r.label,
              cells: [
                r.label,
                r.amount_usd === null ? "" : whole(r.amount_usd),
                <span key="r" className="flex items-center gap-[8px]">
                  <StatusDisc state={r.outcome === "within_threshold" ? "done" : "todo"} />
                  <span className={cn(r.outcome !== "within_threshold" && "text-amber-ink")}>
                    {r.outcome === "within_threshold"
                      ? c.within(r.detail ?? "")
                      : c.held(r.detail ?? "")}
                  </span>
                </span>,
              ],
            }))}
            footer={
              <div className="flex flex-col gap-[4px] px-[12px] py-[8px] text-dense">
                {within.length > 0 && (
                  <span data-total="within">
                    {c.totalWithin(within.length, sum(within), within[0]?.approver_name ?? "")}
                  </span>
                )}
                {held.length > 0 && (
                  <span data-total="held">
                    {c.totalHeld(held.length, sum(held), held[0]?.approver_name ?? "")}
                  </span>
                )}
                <Planned label={c.openAjes} hint={c.plannedAjes} />
              </div>
            }
          />
        )}
      </Fieldset>
      {timeline}
    </>
  );
}

// --- b · Review checklists ---------------------------------------------------------------------

const RUN_DISC = { passed: "done", exceptions: "fail", running: "run" } as const;

function ChecklistsSection({
  standards,
  selected,
  examples,
}: {
  standards: readonly StandardOut[];
  selected: string | undefined;
  examples: StandardExamplesOut | undefined;
}): JSX.Element {
  const c = COPY.checklists;
  const year = standards[0]?.current_version?.tax_year ?? null;
  const total = standards.reduce((t, s) => t + (s.usage_count ?? 0), 0);
  const drafts = standards.filter((s) => s.draft_version !== null);
  const rows = [
    ...standards.map((s) => ({
      key: s.id,
      selected: s.key === selected,
      cells: [
        s.name,
        s.entries === null || s.entries === undefined ? "—" : String(s.entries),
        s.current_version === null ? "—" : COPY.version(s.current_version.version),
        s.usage_count === null ? "—" : c.returns(s.usage_count),
        s.owner.name,
      ],
    })),
    {
      key: "total",
      cells: [
        <span key="t" className="font-medium">
          {c.total}
        </span>,
        "",
        "",
        <span key="n" className="font-medium">
          {year === null ? String(total) : c.totalReturns(total, year)}
        </span>,
        "",
      ],
    },
    ...drafts.map((s) => {
      const d = s.draft_version as StandardVersionSummaryOut;
      return {
        key: `${s.id}-draft`,
        muted: true,
        cells: [
          c.draftRow(s.name, d.version, d.tax_year ?? null),
          "—",
          COPY.version(d.version),
          <Pill key="p" variant="neutral" size="micro">
            {c.draft}
          </Pill>,
          s.owner.name,
        ],
      };
    }),
  ];
  return (
    <>
      <Fieldset
        flush
        title={c.title}
        action={year === null ? undefined : <Meta>{c.meta(year)}</Meta>}
      >
        <Grid
          label={c.title}
          head={c.head}
          cols="minmax(0,1.6fr) 60px 70px minmax(0,1fr) minmax(0,0.8fr)"
          right={[1, 3]}
          rows={rows}
        />
      </Fieldset>
      {examples?.provider_registered === true && (
        <section
          aria-label={c.card}
          data-run-card=""
          className="mb-[10px] overflow-hidden rounded-nested bg-card shadow-e1"
        >
          <div className="flex flex-col items-center gap-[6px] border-b-[0.5px] border-hair py-[10px]">
            <span className="rounded-full bg-card px-[14px] py-[4px] text-nav font-medium shadow-e1">
              {c.card}
            </span>
            {examples.caption !== null && (
              <span className="text-meta text-ink-3">{examples.caption}</span>
            )}
          </div>
          <ul className="divide-y-[0.5px] divide-hair">
            {examples.rows.map((r) => {
              const outcome = r.outcome as keyof typeof RUN_DISC;
              return (
                <li key={r.label} className="flex min-h-[34px] items-center gap-[8px] px-[12px]">
                  <StatusDisc state={RUN_DISC[outcome]} />
                  <span className="flex-1 text-body">{r.label}</span>
                  {outcome === "exceptions" ? (
                    <Pill variant="red-tint" size="micro">
                      {c.exceptions(r.detail ?? "")}
                    </Pill>
                  ) : (
                    <span className="text-dense text-ink-2">
                      {outcome === "running"
                        ? c.running(r.detail ?? "")
                        : r.detail === null
                          ? c.passed
                          : `${c.passed} · ${r.detail}`}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="flex justify-end px-[12px] py-[8px]">
            <Planned label={c.openRun} hint={c.plannedRun} />
          </div>
        </section>
      )}
    </>
  );
}

// --- c · Review levels -------------------------------------------------------------------------

function LevelsSection({
  payload,
  title,
  owner,
}: {
  payload: Of<"review_levels">;
  title: string;
  owner: string;
}): JSX.Element {
  const c = COPY.levels;
  const name = (l: keyof typeof c.names) => `${c.names[l]} (${l})`;
  const rows = payload.tiers.map((t, i) => {
    const before = i === 0 ? [] : (payload.tiers[i - 1]?.required_levels ?? []);
    const added = t.required_levels.filter((l) => !before.includes(l));
    const signOffs =
      i === 0
        ? t.required_levels.map(name).join(" → ")
        : [...added.map(name), ...(t.second_partner_review ? [c.secondPartner] : [])]
            .map((s) => `+ ${s}`)
            .join(" ");
    return {
      key: String(t.tier),
      cells: [
        <span key="t" className="font-medium">
          {c.tier(t.tier, t.name)}
        </span>,
        signOffs,
        <span key="w" className="text-ink-2">
          {t.criteria}
        </span>,
      ],
    };
  });
  return (
    <Fieldset flush title={title} action={<Meta>{COPY.owner(owner)}</Meta>}>
      <Grid
        label={title}
        head={c.head}
        cols="minmax(0,0.8fr) minmax(0,1.2fr) minmax(0,1.6fr)"
        rows={rows}
        footer={<Helper>{c.helper}</Helper>}
      />
    </Fieldset>
  );
}

// --- d · Return approval -----------------------------------------------------------------------

function KeyRows({ rows }: { rows: readonly [string, ReactNode][] }): JSX.Element {
  return (
    <dl className="divide-y-[0.5px] divide-hair">
      {rows.map(([k, v]) => (
        <div
          key={k}
          className="grid grid-cols-[170px_minmax(0,1fr)] gap-[12px] px-[12px] py-[9px]"
        >
          <dt className="text-body text-ink-2">{k}</dt>
          <dd className="text-body">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function ApprovalSection({
  payload,
  owner,
  labels,
}: {
  payload: Of<"return_approval_policy">;
  owner: string;
  labels: Readonly<Record<string, string>>;
}): JSX.Element {
  const c = COPY.approval;
  // A walled client has no label: its entry is absent, with no count (DEC-43, US-3.6).
  const visible = payload.applies_to.filter((a) => labels[a.client_id] !== undefined);
  const approvers = [...new Set(visible.map((a) => labels[a.approver_user_id] ?? ""))];
  const appliesTo = `${visible.map((a) => labels[a.client_id]).join(" · ")} → ${approvers.join(", ")}`;
  return (
    <Fieldset flush title={payload.code} action={<Meta>{COPY.owner(owner)}</Meta>}>
      <KeyRows
        rows={[
          [c.rule, c.rules[payload.rule] ?? payload.rule],
          [c.appliesTo, appliesTo],
          [c.export, c.exports[payload.export_condition] ?? payload.export_condition],
        ]}
      />
      <Helper>{c.helper}</Helper>
    </Fieldset>
  );
}

// --- e · Variance thresholds -------------------------------------------------------------------

function VarianceSection({
  payload,
  title,
  owner,
  examples,
}: {
  payload: Of<"variance_thresholds">;
  title: string;
  owner: string;
  examples: StandardExamplesOut | undefined;
}): JSX.Element {
  const c = COPY.variance;
  return (
    <>
      <Fieldset flush title={title} action={<Meta>{COPY.owner(owner)}</Meta>}>
        <Grid
          label={title}
          head={c.head}
          cols="minmax(0,1.6fr) 70px 90px minmax(0,1.1fr)"
          right={[1, 2]}
          rows={payload.rows.map((r) => ({
            key: r.context,
            cells: [
              c.contexts[r.context] ?? r.context,
              percent(r.pct),
              dollars(r.amount_usd),
              c.both,
            ],
          }))}
        />
      </Fieldset>
      <Fieldset flush title={c.example}>
        {examples?.provider_registered === true && examples.rows.length > 0 ? (
          examples.rows.map((r) => <ExampleLine key={r.label} row={r} />)
        ) : (
          <ExamplesEmpty />
        )}
      </Fieldset>
    </>
  );
}

// --- f · Materiality ranges --------------------------------------------------------------------

function MaterialitySection({
  payload,
  title,
  owner,
  examples,
}: {
  payload: Of<"materiality_ranges">;
  title: string;
  owner: string;
  examples: StandardExamplesOut | undefined;
}): JSX.Element {
  const c = COPY.materiality;
  const range = (lo: string, hi: string) => `${percent(lo)}–${percent(hi)}`;
  const pm = payload.performance_materiality;
  const rows = [
    ...payload.rows.map((r) => ({
      key: r.engagement_kind,
      cells: [r.engagement_kind, r.benchmark, range(r.low_pct, r.high_pct)],
    })),
    { key: "pm", cells: [c.performance, c.ofMateriality, range(pm.low_pct, pm.high_pct)] },
    {
      key: "ct",
      cells: [c.clearlyTrivial, c.ofMateriality, percent(payload.clearly_trivial_pct)],
    },
  ];
  const ex = examples?.provider_registered === true ? examples.rows : [];
  return (
    <>
      <Fieldset flush title={title} action={<Meta>{COPY.owner(owner)}</Meta>}>
        <Grid
          label={title}
          head={c.head}
          cols="minmax(0,1fr) minmax(0,1.2fr) 90px"
          right={[2]}
          rows={rows}
          footer={<Helper>{c.reserved}</Helper>}
        />
      </Fieldset>
      <Fieldset flush title={c.engagements}>
        {ex.length === 0 ? (
          <ExamplesEmpty />
        ) : (
          <Grid
            label={c.engagements}
            head={c.engagementsHead}
            cols="minmax(0,1.5fr) 90px 110px 100px minmax(0,1.1fr)"
            right={[1, 2, 3]}
            rows={ex.map((r) => ({
              key: r.label,
              cells: [
                <span key="e" className="flex flex-col gap-[2px]">
                  <span>{r.label}</span>
                  <span className="text-meta text-ink-2">{r.detail}</span>
                </span>,
                r.amount_usd === null ? "" : dollars(r.amount_usd),
                r.cells?.performance ?? "",
                r.cells?.clearly_trivial ?? "",
                <span key="s" className="flex flex-col items-start gap-[3px]">
                  {r.outcome === "decided" ? (
                    <>
                      <Pill variant="green-tint" size="micro">
                        {c.decided}
                      </Pill>
                      <span className="text-meta text-ink-2">
                        {[r.approver_name, r.cells?.decided_at].filter(Boolean).join(" · ")}
                      </span>
                    </>
                  ) : (
                    <>
                      <Pill variant="amber" size="micro">
                        {c.blocked}
                      </Pill>
                      <span className="text-meta text-ink-2">
                        {c.waiting(r.approver_name ?? "")}
                      </span>
                    </>
                  )}
                </span>,
              ],
            }))}
          />
        )}
      </Fieldset>
    </>
  );
}

// --- g · Document confidence -------------------------------------------------------------------

function ConfidenceSection({
  payload,
  title,
  owner,
  examples,
}: {
  payload: Of<"document_confidence">;
  title: string;
  owner: string;
  examples: StandardExamplesOut | undefined;
}): JSX.Element {
  const c = COPY.confidence;
  return (
    <>
      <Fieldset flush title={title} action={<Meta>{COPY.owner(owner)}</Meta>}>
        <KeyRows
          rows={[
            [c.hold, c.holdValue(payload.hold_below_pct)],
            [c.auto, c.autoValue(payload.auto_accept_above_pct)],
          ]}
        />
        <div className="border-t-[0.5px] border-hair">
          <DisplayToggle
            label={c.autoToggle(payload.auto_accept_above_pct)}
            helper={c.autoHelper}
          />
        </div>
      </Fieldset>
      <Fieldset flush title={c.example}>
        {examples?.provider_registered === true && examples.rows.length > 0 ? (
          examples.rows.map((r) => <ExampleLine key={r.label} row={r} />)
        ) : (
          <ExamplesEmpty />
        )}
      </Fieldset>
    </>
  );
}

// --- h · SSARS & CAS ---------------------------------------------------------------------------

function SsarsSection({
  owner,
  examples,
}: {
  owner: string;
  examples: StandardExamplesOut | undefined;
}): JSX.Element {
  const c = COPY.ssars;
  const ex = examples?.provider_registered === true ? examples.rows : [];
  return (
    <Fieldset flush title={c.title} action={<Meta>{COPY.owner(owner)}</Meta>}>
      <DisplayToggle label={c.toggle} helper={c.helper} />
      {ex.length > 0 && (
        <div className="border-t-[0.5px] border-hair">
          <KeyRows
            rows={ex.map(
              (r) => [r.label, c.frameworks[r.outcome] ?? r.outcome] as [string, string],
            )}
          />
        </div>
      )}
    </Fieldset>
  );
}

// --- the screen --------------------------------------------------------------------------------

function VersionsTimeline({
  timeline,
  now,
}: {
  timeline: readonly StandardVersionSummaryOut[];
  now: number;
}): JSX.Element | null {
  if (timeline.length < 2) return null;
  return (
    <Fieldset flush title={COPY.versions}>
      <Timeline
        label={COPY.versions}
        className="m-0 shadow-none"
        events={timeline.map((v) => ({
          id: v.id,
          date: v.published_at === null ? "" : date(v.published_at, { now, withYear: true }),
          // Superseded is the registry's derived code: published, and not the version in effect.
          state: v.status === "draft" ? "half" : v.current ? "done" : "off",
          title: COPY.version(v.version),
          detail: COPY.timeline(
            v.status === "draft" ? "draft" : v.current ? "published" : "superseded",
            v.current,
          ),
        }))}
      />
    </Fieldset>
  );
}

function Body({
  section,
  standards,
  detail,
  examples,
  checklist,
  now,
}: {
  section: Section;
  standards: readonly StandardOut[];
  detail: StandardDetailOut | undefined;
  examples: StandardExamplesOut | undefined;
  checklist: string | undefined;
  now: number;
}): JSX.Element | null {
  if (section === "review_checklists") {
    return <ChecklistsSection standards={standards} selected={checklist} examples={examples} />;
  }
  if (detail?.version == null) return null;
  const payload = detail.version.payload;
  const owner = detail.standard.owner.name;
  const v = detail.version.version;
  const title = `BH ${detail.standard.name.charAt(0).toLowerCase()}${detail.standard.name.slice(1)} ${COPY.version(v)}`;
  switch (payload.kind) {
    case "aje_thresholds":
      return (
        <AjeSection
          payload={payload}
          title={`BH AJE thresholds ${COPY.version(v)}`}
          owner={owner}
          version={v}
          examples={examples}
          timeline={<VersionsTimeline timeline={detail.timeline} now={now} />}
        />
      );
    case "review_levels":
      return <LevelsSection payload={payload} title={title} owner={owner} />;
    case "return_approval_policy":
      return <ApprovalSection payload={payload} owner={owner} labels={detail.labels ?? {}} />;
    case "variance_thresholds":
      return <VarianceSection payload={payload} title={title} owner={owner} examples={examples} />;
    case "materiality_ranges":
      return (
        <MaterialitySection payload={payload} title={title} owner={owner} examples={examples} />
      );
    case "document_confidence":
      return (
        <ConfidenceSection payload={payload} title={title} owner={owner} examples={examples} />
      );
    case "ssars_cas_settings":
      return <SsarsSection owner={owner} examples={examples} />;
    case "review_checklist":
      return null;
  }
}

function HeaderChips({
  section,
  standards,
  detail,
  now,
}: {
  section: Section;
  standards: readonly StandardOut[];
  detail: StandardDetailOut | undefined;
  now: number;
}): JSX.Element | null {
  if (section === "review_checklists") {
    const owners = [...new Set(standards.map((s) => s.owner.name))];
    return owners.length === 1 ? (
      <Pill variant="green-tint">{COPY.publishedOwner(owners[0] ?? "")}</Pill>
    ) : null;
  }
  const current = detail?.standard.current_version;
  if (detail?.version == null || current == null) return null;
  const payload = detail.version.payload;
  const chip =
    payload.kind === "return_approval_policy" ? payload.code : COPY.version(current.version);
  return (
    <span className="flex items-center gap-[8px]">
      <span
        data-version-chip=""
        className="rounded-full bg-chip px-[7px] py-[1px] text-pill-sm text-ink-2"
      >
        {chip}
      </span>
      {current.published_at !== null && current.published_by !== null && (
        <Pill variant="green-tint">
          {COPY.published(
            date(current.published_at, { now, withYear: true }),
            current.published_by.name,
          )}
        </Pill>
      )}
    </span>
  );
}

export function KNW04({ initial = {}, onBack, onSection, onNewVersion }: Knw04Props): JSX.Element {
  const on = useFlag("knowledge.firm_standards") === true;
  const now = useNow().getTime();
  const firm = useSession().tenant?.firm_name ?? "";
  const [current, setSection] = useState<KnwSection>(
    initial.section === DEADLINE
      ? DEADLINE
      : (SECTIONS.find((s) => s.id === initial.section)?.id ?? DEFAULT_SECTION),
  );
  const rules = current === DEADLINE;
  // On j the standards reads stay idle; `section` keeps the standards sections' type for them.
  const section: Section = current === DEADLINE ? DEFAULT_SECTION : current;
  const kind = SECTIONS.find((s) => s.id === section)?.kind ?? "aje_thresholds";
  const list = useQuery({
    ...listStandardsOptions({ query: { kind } }),
    enabled: on && !rules,
  });
  const standards = list.data?.items ?? [];
  const chosen =
    section === "review_checklists"
      ? (standards.find((s) => s.key === initial.checklist) ?? undefined)
      : standards[0];
  const detail = useQuery({
    ...standardOptions({ path: { standard_id: chosen?.id ?? "" } }),
    enabled: on && !rules && chosen !== undefined && section !== "review_checklists",
  });
  const examples = useQuery({
    ...standardExamplesOptions({
      path: { standard_id: chosen?.id ?? "" },
      query: { period: PERIOD },
    }),
    enabled: on && !rules && chosen !== undefined,
  });

  const groups = [
    {
      label: COPY.group,
      sections: [
        ...SECTIONS.map(({ id, label, icon }) => ({ id, label, icon })),
        { id: DEADLINE, label: DEADLINE_COPY.label, icon: "calendar-clock" as const },
      ],
    },
  ];
  const owner = chosen?.allowed_actions.includes("firm_standard.draft") === true;
  const draftOpen = owner && chosen.draft_version != null && section !== "review_checklists";
  const canDraft = owner && !draftOpen;
  const newVersion = useNewVersion(chosen?.id);
  const actions = (
    <span className="flex items-center gap-[8px]">
      <Button
        variant="secondary"
        disabled={!canDraft}
        onClick={() => {
          if (chosen === undefined) return;
          if (onNewVersion !== undefined) onNewVersion(chosen.id);
          else newVersion.start();
        }}
      >
        {COPY.newVersion}
      </Button>
      <Button
        variant="secondary"
        disabled={section !== "review_checklists" || !PLANNED_VISIBLE}
        title={section === "review_checklists" ? COPY.checklists.plannedRun : undefined}
      >
        {COPY.apply}
      </Button>
    </span>
  );

  let body: ReactNode;
  if (!on) {
    body = <FlagOffState flag="knowledge.firm_standards" label={COPY.flagLabel} icon="scale" />;
  } else if (rules) {
    body = <DeadlineRulesSection />;
  } else if (list.isError || detail.isError) {
    body = (
      <ErrorState
        title={COPY.error}
        retryLabel={COPY.retry}
        onRetry={() => {
          void list.refetch();
          void detail.refetch();
        }}
      />
    );
  } else if (list.isPending || (section !== "review_checklists" && detail.isPending)) {
    body = (
      <div aria-busy="true" aria-label={COPY.loading} className="flex flex-col gap-[10px]">
        <Skeleton className="h-[160px]" />
        <Skeleton className="h-[90px]" />
      </div>
    );
  } else if (draftOpen) {
    body = (
      <DraftPane
        standard={chosen}
        title={section === "aje_thresholds" ? "BH AJE thresholds v{v}" : `BH ${chosen.name} v{v}`}
        current={detail.data?.version ?? null}
        now={now}
        onClosed={() => {
          void list.refetch();
          void detail.refetch();
        }}
      />
    );
  } else {
    body = (
      <Body
        section={section}
        standards={standards}
        detail={detail.data}
        examples={examples.data}
        checklist={initial.checklist}
        now={now}
      />
    );
  }

  return (
    <SettingsLayout
      bare
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={firm}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
      navTitle={COPY.navTitle}
      groups={groups}
      active={current}
      onSelect={(id) => {
        const next = id as KnwSection;
        setSection(next);
        onSection?.(next);
      }}
      dirty={false}
      readOnly={false}
      headerCenter={
        on && !rules ? (
          draftOpen && chosen.draft_version != null ? (
            <span className="flex items-center gap-[8px]">
              <span className="rounded-full bg-chip px-[7px] py-[1px] text-pill-sm text-ink-2">
                {COPY.version(chosen.draft_version.version)}
              </span>
              {DRAFT_PILL(chosen.draft_version.version)}
            </span>
          ) : (
            <HeaderChips section={section} standards={standards} detail={detail.data} now={now} />
          )
        ) : undefined
      }
      headerActions={on && !rules ? actions : <span />}
    >
      <div data-screen="KNW-04" data-section={current} className="flex flex-col">
        {body}
      </div>
    </SettingsLayout>
  );
}
