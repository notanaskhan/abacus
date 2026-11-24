// ADM-12 · Monitoring & inspections (Q-05-T23; TASK-8933; docs/screens/ADM-12.md; handoff ADM-12
// a–g; SPEC-711; DEC-5935): T1 in the T12 settings frame, Margaret Okonkwo. Every count, date and
// word is the server's (`/v1/quality/cycles`, `/inspections`, `/inspection-candidates`,
// `/findings`, `/evaluations/{year}`); the browser formats and filters, never adds a figure.
//   a default · b Select engagements… (candidates with risk scores and the objectivity check)
//   c Record finding… · d Conclude evaluation (SHL-11 decision card, Dec 14) · e empty 2027 cycle
//   f concluded · g QM-F-02's detail with its actions.
// Inspection rows open the engagement's archived record (AUD-25) read-only; no agent decides a
// finding or the evaluation (the decision card is reserved to the person).
import type { QualityFindingOut, QualityInspectionOut } from "@abacus/api-client";
import {
  qualityCandidatesOptions,
  qualityCyclesOptions,
  qualityEvaluationOptions,
  qualityEvaluationRequestMutation,
  qualityFindingsOptions,
  qualityInspectionsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  DecisionCard,
  EmptyState,
  FilterChip,
  Picker,
  Pill,
  SettingsLayout,
  SearchField,
  SheetModal,
  Skeleton,
  StatusDisc,
  StatusTile,
  Tag,
  Tooltip,
  cn,
  date,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenHref } from "../../app-core/open";
import { hrefOf, to } from "../../routes/to";
import { GROUPS } from "../ADM-01/copy";
import { COPY as C } from "./copy";

export interface ADM12Props {
  /** b, c: a sheet open on arrival; d: the decision card. */
  open?: "select" | "finding" | "decide";
  /** e: the 2027 cycle selected. */
  cycle?: 2026 | 2027;
  /** g: the finding whose detail is scrolled to its actions. */
  finding?: string;
  /** Another settings section by id (the T12 frame's nav). */
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

const WIDTHS = [84, 230, 150, 70, 76, 220, 70, 140, 64] as const;
const STATUS_PILL: Record<QualityInspectionOut["status"], "neutral" | "amber" | "green"> = {
  planned: "neutral",
  in_progress: "amber",
  concluded: "green",
};

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .slice(0, 2);
}

function InspectionRow({
  r,
  now,
  onOpen,
}: {
  r: QualityInspectionOut;
  now: Date;
  /** Opens the inspected record read-only (DV-8); absent while its screen is planned. */
  onOpen?: (() => void) | undefined;
}): JSX.Element {
  const status =
    r.status === "concluded" && r.concluded_on
      ? C.concludedOn(date(r.concluded_on, { now }))
      : {
          planned: C.tiles.planned,
          in_progress: C.tiles.inProgress,
          concluded: C.tiles.concluded,
        }[r.status];
  return (
    <tr className="h-[40px] hairline-b text-[12.5px]" data-inspection={r.ref}>
      <td className="px-[8px] font-mono text-[11.5px]">{r.ref}</td>
      <td className="px-[8px]">
        {onOpen ? (
          <button
            type="button"
            className="block text-left text-[13px] font-medium hover:underline"
            onClick={onOpen}
          >
            {r.engagement_name}
          </button>
        ) : (
          <span className="block text-[13px] font-medium">{r.engagement_name}</span>
        )}
        {r.engagement_line ? (
          <span className="text-[11.5px] text-ink-3">{r.engagement_line}</span>
        ) : null}
      </td>
      <td className="px-[8px]">{r.kind}</td>
      <td className="px-[8px]" title={r.signer?.name}>
        {r.signer ? initials(r.signer.name) : DASH}
      </td>
      <td className="px-[8px]" title={r.inspector.name}>
        {initials(r.inspector.name)}
      </td>
      <td className="px-[8px] text-ink-2">{r.selected_because ?? DASH}</td>
      <td className="px-[8px]">{r.due_on ? date(r.due_on, { now }) : DASH}</td>
      <td className="px-[8px]">
        <Pill variant={STATUS_PILL[r.status]} size="sm">
          {status}
        </Pill>
      </td>
      <td className="px-[8px] text-right tabular-nums">
        {r.status === "planned" ? DASH : r.findings}
      </td>
    </tr>
  );
}

function FindingDetail({ f, now }: { f: QualityFindingOut; now: Date }): JSX.Element {
  const kv: [string, string | null | undefined][] = [
    [C.kv.inspection, f.inspection_ref],
    [
      C.kv.evaluation,
      f.evaluation
        ? `${C.evaluationWords[f.evaluation] ?? f.evaluation}${f.evaluated_by ? ` (${f.evaluated_by}${f.evaluated_on ? `, ${date(f.evaluated_on, { now })}` : ""})` : ""}`
        : C.evaluationWords.finding_open,
    ],
    [C.kv.rootCause, f.root_cause],
    [C.kv.remediation, f.remediation],
    [C.kv.owner, f.owner?.name],
    [C.kv.due, f.due_on ? date(f.due_on, { now, withYear: true }) : null],
  ];
  return (
    <div className="flex min-w-0 flex-1 flex-col" data-adm12="finding-detail">
      <h3 className="bg-shell px-[14px] py-[10px] text-[15px] font-medium">{f.title}</h3>
      <dl className="flex-1 overflow-auto">
        {kv.map(([k, v]) => (
          <div
            key={k}
            className="flex min-h-[35px] gap-[12px] px-[14px] py-[7px] hairline-b text-[12.5px]"
          >
            <dt className="w-[110px] flex-none text-ink-2">{k}</dt>
            <dd className="flex-1">
              {k === C.kv.rootCause && f.root_cause_category ? (
                <Tag className="mr-[6px]">
                  {C.rootCauses[f.root_cause_category] ?? f.root_cause_category}
                </Tag>
              ) : null}
              {v ?? DASH}
            </dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-col gap-[6px] p-[10px]" data-adm12="finding-actions">
        <Button variant="primary">{C.markRemediated}</Button>
        <Button variant="tonal">{C.openStep}</Button>
        <Button variant="tonal">{C.addTask}</Button>
      </div>
    </div>
  );
}

export function ADM12(props: ADM12Props): JSX.Element {
  const openHref = useOpenHref();
  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={C.title}
      context=""
      backLabel={C.back}
      onBack={props.onBack ?? (() => undefined)}
      navTitle={C.navTitle}
      groups={GROUPS}
      active="monitoring"
      onSelect={(id) => {
        // Built settings screens open through the manifest's builders (T-01-T51).
        if (id === "general") openHref(hrefOf(to.ADM01()));
        else if (id === "consents") openHref(hrefOf(to.ADM05()));
        else if (id === "integrations") openHref(hrefOf(to.ADM08()));
        else if (id !== "monitoring") props.onNavigate?.(id);
      }}
      dirty={false}
    >
      <Monitoring {...props} />
    </SettingsLayout>
  );
}

function Monitoring({ open, cycle: initialCycle = 2026, finding }: ADM12Props): JSX.Element {
  const now = useNow();
  const openHref = useOpenHref();
  const queries = useQueryClient();
  const [cycle, setCycle] = useState<2026 | 2027>(initialCycle);
  const [sheet, setSheet] = useState(open ?? null);
  const [selected, setSelected] = useState<string | null>(finding ?? null);
  const [search, setSearch] = useState("");
  const [choice, setChoice] = useState("reasonable");
  const cycles = useQuery(qualityCyclesOptions());
  const insp = useQuery(qualityInspectionsOptions({ query: { cycle } }));
  const fin = useQuery(qualityFindingsOptions({ query: { cycle } }));
  const evaluation = useQuery(qualityEvaluationOptions({ path: { year: cycle } }));
  const candidates = useQuery({
    ...qualityCandidatesOptions({ query: { cycle } }),
    enabled: sheet === "select",
  });
  const conclude = useMutation({
    ...qualityEvaluationRequestMutation(),
    onSuccess: async () => {
      setSheet(null);
      await queries.invalidateQueries();
    },
  });
  if (insp.isError || cycles.isError) {
    return (
      <div data-screen="ADM-12" role="alert" className="p-[24px]">
        <p className="text-[13px]">{C.failed}</p>
        <Button variant="secondary" size="sm" onClick={() => void insp.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  if (insp.data === undefined || cycles.data === undefined) {
    return (
      <div data-screen="ADM-12" aria-busy="true">
        <Skeleton className="h-[700px] w-full" />
      </div>
    );
  }
  const row = cycles.data.items.find((c) => c.year === cycle);
  const rows = insp.data.items.filter((r) =>
    search === ""
      ? true
      : `${r.ref} ${r.engagement_name}`.toLowerCase().includes(search.toLowerCase()),
  );
  const findings = fin.data?.items ?? [];
  const current = findings.find((f) => f.ref === selected) ?? findings[1] ?? findings[0];
  const ev = evaluation.data;
  const total = insp.data.items.length;
  const concludedN = row?.concluded ?? 0;
  const days = ev?.as_of
    ? Math.max(0, Math.round((Date.parse(ev.as_of) - now.getTime()) / 86_400_000))
    : null;
  return (
    <div data-screen="ADM-12" className="flex min-h-0 flex-1 flex-col gap-[8px] p-[12px]">
      <div className="flex h-[34px] items-center gap-[8px]" data-adm12="filters">
        <FilterChip
          label={C.cycle}
          icon="calendar"
          options={cycles.data.items.map((c) => ({
            value: String(c.year),
            label: String(c.year),
          }))}
          value={String(cycle)}
          onChange={(v) => {
            setCycle(v === "2027" ? 2027 : 2026);
          }}
        />
        <FilterChip label={C.type} icon="layers" options={[]} placeholder={C.all} />
        <FilterChip label={C.inspector} icon="user" options={[]} placeholder={C.all} />
        <span className="flex-1" />
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setSheet("select");
          }}
        >
          {C.selectEngagements}
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            setSheet("finding");
          }}
        >
          {C.recordFinding}
        </Button>
      </div>
      {total === 0 ? (
        <EmptyState icon="calendar" title={C.empty.title}>
          {C.empty.body}
        </EmptyState>
      ) : (
        <>
          <div className="flex gap-[8px]" data-adm12="tiles">
            <StatusTile count={row?.planned ?? 0} label={C.tiles.planned} variant="neutral" />
            <StatusTile count={row?.in_progress ?? 0} label={C.tiles.inProgress} variant="state" />
            <StatusTile count={concludedN} label={C.tiles.concluded} variant="green" />
            <StatusTile
              count={row?.findings_open ?? 0}
              label={C.tiles.findingsOpen}
              variant="red-tint"
            />
          </div>
          <section aria-label={C.plan(cycle)} className="rounded-[12px] bg-card shadow-e2">
            <header className="flex h-[46px] items-center gap-[10px] px-[12px]">
              <span className="w-[220px]">
                <SearchField label={C.search} value={search} onChange={setSearch} />
              </span>
              <h2 className="flex-1 text-center text-[14px] font-medium">{C.plan(cycle)}</h2>
              <span className="text-[12px] text-ink-3">{C.objectivity}</span>
            </header>
            <table className="w-full border-collapse" data-adm12="plan">
              <colgroup>
                {WIDTHS.map((w, i) => (
                  <col key={i} style={{ width: w }} />
                ))}
              </colgroup>
              <thead>
                <tr className="hairline-b">
                  {C.columns.map((h) => (
                    <th
                      key={h}
                      scope="col"
                      className="h-[30px] bg-nested px-[8px] text-left text-[12px] font-normal text-ink-2"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <InspectionRow
                    key={r.inspection_id}
                    r={r}
                    now={now}
                    onOpen={
                      // A tax inspection opens its return (the return id is its work item);
                      // AUD-25 has no route yet, so an audit row opens nothing (DV-8).
                      r.basis === "firm_policy_c230_10_36"
                        ? () => {
                            openHref(hrefOf(to.TAX02({ returnId: r.work_item_id })));
                          }
                        : undefined
                    }
                  />
                ))}
              </tbody>
            </table>
            <p className="px-[12px] pt-[8px] text-[12px] text-ink-3">
              {C.footer(
                total,
                concludedN,
                row?.in_progress ?? 0,
                row?.planned ?? 0,
                insp.data.items.reduce((t, r) => t + (r.findings ?? 0), 0),
              )}
            </p>
            <p className="px-[12px] pb-[8px] text-[11.5px] text-ink-3">{C.footerTax}</p>
          </section>
          <div className="flex min-h-0 gap-[10px]">
            <section
              aria-label={C.findingsPane}
              className="flex w-[784px] overflow-hidden rounded-[12px] bg-card shadow-e2"
            >
              <ul className="w-[330px] flex-none border-r border-hair" data-adm12="findings">
                {findings.map((f) => (
                  <li key={f.finding_id}>
                    <button
                      type="button"
                      aria-current={current?.ref === f.ref ? "true" : undefined}
                      onClick={() => {
                        setSelected(f.ref);
                      }}
                      className={cn(
                        "flex min-h-[60px] w-full gap-[8px] px-[12px] py-[8px] text-left",
                        current?.ref === f.ref && "bg-nested",
                      )}
                      data-finding={f.ref}
                    >
                      <span
                        aria-hidden
                        className={cn(
                          "mt-[4px] size-[8px] flex-none rounded-full",
                          f.evaluation ? "bg-red" : "bg-amber",
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-[12.5px]">{`${f.ref} · ${f.title}`}</span>
                        <span className="text-[11.5px] text-ink-3">
                          {`${f.inspection_ref ?? C.agentMonitoring} · ${f.owner ? initials(f.owner.name) : DASH} · ${f.due_on ? date(f.due_on, { now }) : DASH}`}
                        </span>
                      </span>
                      <Pill variant={f.status === "open" ? "amber" : "neutral"} size="sm">
                        {C.statusWords[f.status]}
                      </Pill>
                    </button>
                  </li>
                ))}
              </ul>
              {current ? <FindingDetail f={current} now={now} /> : null}
            </section>
            {ev ? (
              <section
                aria-label={C.evaluationTitle}
                className="flex flex-1 flex-col gap-[8px] rounded-[12px] bg-card p-[14px] shadow-e1"
                data-adm12="evaluation"
              >
                <h3 className="text-[13.5px] font-medium">{C.evaluationTitle}</h3>
                <dl className="text-[12.5px]">
                  <div className="flex gap-[8px]">
                    <dt className="text-ink-2">{C.asOf}</dt>
                    <dd>{ev.as_of ? date(ev.as_of, { now, withYear: true }) : DASH}</dd>
                  </div>
                  <div className="flex gap-[8px]">
                    <dt className="text-ink-2">{C.responsible}</dt>
                    <dd>{ev.responsible.name}</dd>
                  </div>
                  <div className="flex gap-[8px]">
                    <dt className="text-ink-2">{C.inputs}</dt>
                    <dd>
                      {C.inputsValue(
                        ev.inputs_inspections ?? 0,
                        ev.inputs_findings ?? 0,
                        ev.inputs_objectives ?? 0,
                      )}
                    </dd>
                  </div>
                </dl>
                {ev.status === "concluded" && ev.concluded_at ? (
                  <Pill variant="green-tint" size="sm" data-adm12="concluded">
                    {C.concluded(
                      date(ev.concluded_at, { now, withYear: true }),
                      ev.responsible.name,
                    )}
                  </Pill>
                ) : (
                  <>
                    <p className="flex items-center gap-[6px] text-[12.5px]">
                      <Pill variant="neutral" size="sm">
                        {C.notStarted}
                      </Pill>
                      {days !== null ? (
                        <span className="text-[11.5px] text-ink-3">{C.daysLeft(days)}</span>
                      ) : null}
                    </p>
                    <ul className="flex flex-col gap-[6px] text-[12.5px]" data-adm12="checklist">
                      <li className="flex items-center gap-[6px]">
                        <StatusDisc state="half" size={15} />
                        {C.checklist.inspections(concludedN, total)}
                      </li>
                      <li className="flex items-center gap-[6px]">
                        <StatusDisc state="todo" size={15} />
                        {C.checklist.remediation}
                      </li>
                      <li className="flex items-center gap-[6px]">
                        <StatusDisc state="todo" size={15} />
                        {C.checklist.rootCause}
                      </li>
                      <li className="flex items-center gap-[6px]">
                        <StatusDisc state="todo" size={15} />
                        {C.checklist.memo}
                      </li>
                    </ul>
                    {(ev.allowed_actions ?? []).includes("conclude") &&
                    ev.inspections_open === 0 ? (
                      <Button
                        variant="primary"
                        onClick={() => {
                          setSheet("decide");
                        }}
                      >
                        {C.conclude}
                      </Button>
                    ) : (
                      <Tooltip content={C.concludeLocked}>
                        <span>
                          <Button variant="primary" disabled>
                            {C.conclude}
                          </Button>
                        </span>
                      </Tooltip>
                    )}
                  </>
                )}
              </section>
            ) : null}
          </div>
        </>
      )}
      <SheetModal
        open={sheet === "select"}
        onOpenChange={(o) => {
          if (!o) setSheet(null);
        }}
        title={C.sheetSelect}
      >
        <ul className="flex flex-col gap-[6px] p-[14px]" data-adm12="candidates">
          {(candidates.data?.items ?? []).map((c) => (
            <li key={c.work_item_id} className="flex items-center gap-[8px] text-[12.5px]">
              <input type="checkbox" aria-label={c.engagement_name} />
              <span className="flex-1">
                {c.engagement_name}
                <span className="block text-[11.5px] text-ink-3">{c.selected_because}</span>
              </span>
              <span className="tabular-nums text-ink-2">{`${C.riskScore} ${c.risk_score}`}</span>
            </li>
          ))}
        </ul>
        <p className="px-[14px] text-[12px]">{C.objective("Celia Marsh", "Sterling Freight")}</p>
        <p className="px-[14px] pb-[14px] text-[12px] text-red">
          {C.notObjective("Thomas Whitcombe", "Sterling Freight")}
        </p>
      </SheetModal>
      <SheetModal
        open={sheet === "finding"}
        onOpenChange={(o) => {
          if (!o) setSheet(null);
        }}
        title={C.sheetFinding}
      >
        <form
          className="flex flex-col gap-[8px] p-[14px] text-[12.5px]"
          data-adm12="record-finding"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          {[
            C.fields.inspection,
            C.fields.title,
            C.fields.rootCause,
            C.fields.remediation,
            C.fields.owner,
            C.fields.due,
          ].map((label) => (
            <label key={label} className="flex flex-col gap-[4px]">
              <span className="text-ink-2">{label}</span>
              <input className="h-[30px] rounded-nested bg-nested px-[8px]" aria-label={label} />
            </label>
          ))}
          <div className="flex flex-col gap-[4px]">
            <span className="text-ink-2">{C.fields.evaluation}</span>
            <Picker
              label={C.fields.evaluation}
              options={Object.entries(C.evaluationWords).map(([value, label]) => ({
                value,
                label,
              }))}
              defaultValue="finding_open"
            />
            <span className="text-[11.5px] text-ink-3">{C.evaluationReserved}</span>
          </div>
          <div className="flex justify-end gap-[8px]">
            <Button
              variant="secondary"
              type="button"
              onClick={() => {
                setSheet(null);
              }}
            >
              {C.cancel}
            </Button>
            <Button variant="primary" type="submit">
              {C.save}
            </Button>
          </div>
        </form>
      </SheetModal>
      {sheet === "decide" && ev ? (
        <SheetModal
          open
          onOpenChange={(o) => {
            if (!o) setSheet(null);
          }}
          title={C.decision.title(ev.as_of ? date(ev.as_of, { now, withYear: true }) : "")}
        >
          <div className="p-[14px]" data-adm12="decision">
            <DecisionCard
              variant="sheet"
              title={C.decision.title(ev.as_of ? date(ev.as_of, { now, withYear: true }) : "")}
              reservedNote={C.decision.reserved}
              options={C.decision.options}
              value={choice}
              onChange={setChoice}
              actor={{ kind: "human", name: ev.responsible.name }}
              busy={conclude.isPending}
              onDecide={() => {
                conclude.mutate({
                  path: { year: cycle },
                  headers: { "Idempotency-Key": `adm12-${crypto.randomUUID()}` },
                });
              }}
            />
          </div>
        </SheetModal>
      ) : null}
    </div>
  );
}
