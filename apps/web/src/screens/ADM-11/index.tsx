// ADM-11 · Quality management dashboard (Q-05-T19, TASK-8825; docs/screens/ADM-11.md; handoff
// ADM-11 + R2): T11 in the T12 settings frame. Every figure is code's (`GET /v1/quality/
// dashboard`, `/register`, `/agent-overrides`, `/findings`; DEC-96); the browser formats only.
// a default · b office filter (tiles recompute, objectives firm-wide) · c agent row expanded
// (reasons, Open run history, Open finding, Open learned context) · d before the first inspection
// (no findings, accuracy —) · e read-only (Monitoring reviewer). The agent decides nothing here.
import type { QualityAgentRowOut, QualityObjectiveOut } from "@abacus/api-client";
import {
  consultationsLogOptions,
  qualityDashboardOptions,
  qualityFindingsOptions,
  qualityOverrideReasonsOptions,
  qualityOverridesOptions,
  qualityRegisterOptions,
} from "@abacus/api-client/query";
import { DASH, EmptyState, Pill, Skeleton, cn } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

export interface ADM11Props {
  /** b: the office filter's chip, by the scenario. */
  office?: string;
  /** c: the agent row opened on arrival. */
  expandedAgent?: string;
  readOnly?: boolean;
}

function Tile({ value, pill, tone, caption }: { value: string; pill: string; tone: "amber" | "red-tint" | "green-tint" | "neutral" | "state"; caption: React.ReactNode }): JSX.Element {
  return (
    <div className="flex h-[86px] w-[180px] flex-col items-center justify-center gap-[8px] rounded-[14px] bg-card shadow-e1" data-adm11="tile">
      <span className="text-[22px] tabular-nums">{value}</span>
      <Pill variant={tone === "state" ? "amber" : tone}>{pill}</Pill>
      <span className="text-[11.5px] text-ink-3">{caption}</span>
    </div>
  );
}

function Bar({ rate, tolerance }: { rate: number; tolerance: number }): JSX.Element {
  const over = rate > tolerance;
  return (
    <span className="relative inline-block h-[3px] w-[80px] rounded-full bg-chip" aria-hidden>
      <span className={cn("absolute inset-y-0 left-0 rounded-full", over ? "bg-red" : "bg-cta-deep")} style={{ width: `${String(Math.min(100, rate * 5))}%` }} />
      <span className="absolute -top-[2px] h-[7px] w-px bg-ink-3" style={{ left: `${String(tolerance * 5)}%` }} />
    </span>
  );
}

function Reasons({ agent }: { agent: string }): JSX.Element {
  const found = useQuery(qualityOverrideReasonsOptions({ path: { agent_key: agent } }));
  return (
    <>
      {(found.data?.items ?? []).map((r) => (
        <span key={r.reason_code}>{`${C.reasons[r.reason_code] ?? r.reason_code} ${String(r.count)}`}</span>
      ))}
    </>
  );
}

export function ADM11({ office, expandedAgent, readOnly = false }: ADM11Props): JSX.Element {
  const dash = useQuery(qualityDashboardOptions());
  const reg = useQuery(qualityRegisterOptions());
  const ov = useQuery(qualityOverridesOptions());
  const log = useQuery(consultationsLogOptions());
  const fin = useQuery(qualityFindingsOptions());
  const [open, setOpen] = useState<string | undefined>(expandedAgent);
  if (dash.data === undefined || reg.data === undefined || ov.data === undefined || fin.data === undefined) {
    return <Skeleton aria-label={C.title} className="h-[760px] w-full" />;
  }
  const t = dash.data.tiles;
  const objectives = reg.data.objectives;
  const notes = Object.fromEntries(dash.data.components.map((c) => [c.component, c.signals[0] ?? null]));
  const open_ = (log.data?.items ?? []).filter((c) => c.status === "open");
  const atRisk = objectives.filter((o: QualityObjectiveOut) => o.health_flag === "at_risk").length;
  const inspections = fin.data.items.filter((f) => f.source === "inspection").length;
  const agents = fin.data.items.length - inspections;
  return (
    <div data-screen="ADM-11" data-readonly={readOnly} className="flex flex-col gap-[10px]">
      <div className="flex h-[34px] items-center justify-between">
        <h1 className="flex items-center gap-[8px] text-[15px] font-medium">
          {C.title} <span className="font-normal text-ink-2">{C.sqms}</span>
          <span className="rounded-pill bg-chip px-[8px] text-[12.5px] font-normal text-ink-2">{C.year}</span>
        </h1>
        <span className={cn("rounded-pill px-[10px] py-[4px] text-[12.5px] shadow-e1", office ? "bg-amber-tint" : "bg-card")} data-adm11="office">
          {`${C.office} │ ${office ?? C.allOffices}`}
        </span>
      </div>
      <div className="flex gap-[9px]">
        <Tile value={String(t.objectives_at_risk)} pill={C.tiles.atRisk} tone="amber" caption={C.of(t.objectives)} />
        <Tile value={String(t.findings_open)} pill={C.tiles.findings} tone="red-tint" caption={C.findingsSub(inspections, agents)} />
        <Tile value={t.override_rate === null ? DASH : `${t.override_rate}%`} pill={C.tiles.override} tone="green-tint"
          caption={<>{C.overrideSub(t.overrides, t.outputs, t.tolerance_pct)}<a className="underline" href="/insights/ai-adoption">{C.insights}</a></>} />
        <Tile value={t.accuracy === null ? DASH : `${t.accuracy}%`} pill={C.tiles.accuracy} tone="green-tint" caption={C.accuracySub} />
        <Tile value={String(t.consultations_open)} pill={C.tiles.consultations} tone="neutral" caption="C-01 · C-05" />
        <Tile value={C.days(t.days_to_evaluation)} pill={C.tiles.evaluation} tone="state" caption={C.due} />
      </div>
      <div className="flex gap-[10px]">
        <section aria-label={C.objectivesPane} className="flex-[696] rounded-card bg-card shadow-e1">
          <h2 className="flex h-[46px] items-center justify-center text-[13.5px] font-medium">{C.objectivesPane}</h2>
          <table className="w-full text-[13px]">
            <thead><tr className="h-[30px] bg-nested text-[11.5px] text-ink-2">{C.columns.map((c) => <th key={c} className="px-[10px] text-left font-medium">{c}</th>)}</tr></thead>
            <tbody>
              {objectives.map((o: QualityObjectiveOut) => (
                <tr key={o.objective_id} className="border-t border-hair align-top">
                  <td className="px-[10px] py-[8px]">
                    {C.components[o.component] ?? o.title}
                    {o.health_flag === "at_risk" && notes[o.component] ? <div className="text-[11.5px] text-ink-3">{notes[o.component]}</div> : null}
                  </td>
                  <td className="px-[10px] py-[8px] tabular-nums">{String((o as unknown as { objectives?: number }).objectives ?? 1)}</td>
                  <td className="px-[10px] py-[8px] tabular-nums">{o.risks}</td>
                  <td className="px-[10px] py-[8px] tabular-nums">{o.responses}</td>
                  <td className="px-[10px] py-[8px]"><Pill variant={o.health_flag === "at_risk" ? "amber" : "green-tint"}>{o.health_flag === "at_risk" ? C.atRiskPill : C.onTrack}</Pill></td>
                  <td className="px-[10px] py-[8px]">{o.owner?.name ?? DASH}</td>
                </tr>
              ))}
              <tr className="border-t border-stroke font-medium" data-adm11="totals">
                <td className="px-[10px] py-[8px]" />
                <td className="px-[10px] py-[8px] tabular-nums">{t.objectives}</td>
                <td className="px-[10px] py-[8px] tabular-nums">{reg.data.risks}</td>
                <td className="px-[10px] py-[8px] tabular-nums">{reg.data.responses}</td>
                <td className="px-[10px] py-[8px]">{C.totalsAtRisk(atRisk)}</td>
                <td />
              </tr>
            </tbody>
          </table>
          {office ? <p className="px-[12px] py-[6px] text-[11.5px] text-ink-3">{C.firmWide}</p> : null}
          <h3 className="border-t border-hair bg-band-hd px-[12px] py-[6px] text-[12px] font-medium">{C.processes}</h3>
          <div className="flex h-[40px] items-center justify-between border-t border-hair px-[12px] text-[13px]">{C.riskProcess}<Pill variant="green-tint">{C.current}</Pill></div>
          <div className="flex h-[40px] items-center justify-between border-t border-hair px-[12px] text-[13px]">{C.monitoring}<Pill variant="amber">{C.inProgress}</Pill></div>
        </section>
        <div className="flex flex-[420] flex-col gap-[10px]">
          <section aria-label={C.overridePane} className="rounded-card bg-card shadow-e1">
            <h2 className="flex h-[46px] items-center justify-between px-[12px] text-[13.5px] font-medium">{C.overridePane}<a href="/insights/ai-adoption" className="text-[12.5px]">{`${C.aiAdoption} →`}</a></h2>
            <p className="px-[12px] text-[11.5px] text-ink-3">{C.overrideHelp}</p>
            {ov.data.rows.map((r: QualityAgentRowOut) => (
              <div key={r.agent_key}>
                <button type="button" data-adm11="agent" aria-expanded={open === r.agent_key} onClick={() => { setOpen(open === r.agent_key ? undefined : r.agent_key); }}
                  className="flex h-[40px] w-full items-center gap-[8px] border-t border-hair px-[12px] text-left text-[13px]">
                  <span className="flex-1">{r.label}</span>
                  <span className="tabular-nums">{r.outputs.toLocaleString("en-US")}</span>
                  <span className="tabular-nums">{r.overrides}</span>
                  <span className={cn("w-[44px] text-right tabular-nums", r.above_tolerance && "text-red")}>{`${r.rate ?? DASH}%`}</span>
                  <Bar rate={Number(r.rate ?? 0)} tolerance={Number(ov.data.tolerance_pct)} />
                </button>
                {open === r.agent_key ? (
                  <div className="flex h-[160px] flex-col gap-[6px] bg-nested px-[12px] py-[10px] text-[12.5px]" data-adm11="reasons">
                    <Reasons agent={r.agent_key} />
                    <span className="flex gap-[8px]">
                      <a href="/workbench/runs">{C.openRuns}</a>
                      {r.finding_ref ? <a href="/settings/quality/monitoring">{C.openFinding(r.finding_ref)}</a> : null}
                      <a href="/workbench/learned-context">{C.openLearned}</a>
                    </span>
                  </div>
                ) : null}
              </div>
            ))}
            <div className="flex h-[40px] items-center gap-[8px] border-t border-stroke px-[12px] text-[13px] font-medium" data-adm11="override-total">
              <span className="flex-1">{C.total}</span>
              <span className="tabular-nums">{ov.data.outputs.toLocaleString("en-US")}</span>
              <span className="tabular-nums">{ov.data.overrides}</span>
              <span className="w-[44px] text-right tabular-nums">{`${ov.data.rate ?? DASH}%`}</span>
              <span className="w-[80px]" />
            </div>
            <p className="px-[12px] pt-[6px] text-[11.5px] text-ink-3">{C.unrated(ov.data.unrated)}</p>
            <p className="px-[12px] pb-[8px] text-[11.5px] text-ink-3">{C.sameAsInsights}</p>
          </section>
          <section aria-label={C.findingsPane} className="rounded-card bg-card shadow-e1">
            <h2 className="flex h-[46px] items-center justify-center text-[13.5px] font-medium">{C.findingsPane}</h2>
            {fin.data.items.length === 0 ? (
              <EmptyState title={C.emptyTitle}>{C.emptyBody}</EmptyState>
            ) : (
              fin.data.items.map((f) => (
                <a key={f.finding_id} href="/settings/quality/monitoring" className="flex min-h-[52px] flex-col justify-center border-t border-hair px-[12px] text-[13px]" data-adm11="finding">
                  <span>{`${f.ref} · ${f.title}`}</span>
                  <span className="text-[11.5px] text-ink-3">{`${f.inspection_ref ?? C.agentMonitoring} · ${f.owner?.name ?? ""} · ${C.dueOn(f.due_on ?? "")}`}</span>
                </a>
              ))
            )}
            <h3 className="border-t border-hair bg-band-hd px-[12px] py-[6px] text-[12px] font-medium">{C.consultationsBand(open_.length)}</h3>
            {open_.map((c) => (
              <a key={c.consultation_id} href="/audits/consultations" className="flex min-h-[52px] flex-col justify-center border-t border-hair px-[12px] text-[13px]" data-adm11="consultation">
                <span>{c.ref}</span>
                <span className="text-[11.5px] text-ink-3">{C.consultationSub(c.created_at, c.raised_by_name)}</span>
              </a>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
