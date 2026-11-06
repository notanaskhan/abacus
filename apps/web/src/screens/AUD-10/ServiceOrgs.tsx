import type { CuecOut, ServiceOrganizationOut, SocExceptionOut, SocReportOut } from "@abacus/api-client";
import { serviceOrgsOptions, socReportOptions } from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Button,
  PaneAction,
  Pill,
  type PillVariant,
  Skeleton,
  Spinner,
  cn,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// AUD-10 · Service organizations & SOC 1 (A-04-T37; A-04 §3; AU-C 402; the handoff spec): the Service
// Organizations row's canvas on the T2 audit split: block cards on the well. The coverage timeline
// plots the plan year against the SOC period with the hatched gap, the one pattern the product uses,
// and carries a text alternative. Figures are the server's (A-04-T31's gap, never counted here); the
// browser only places them. Reliance is a partner's decision, so no control concludes it here.

export const SERVICE_ORGS = "service_organizations";
const FLAG = "assurance.service_orgs";
const DAY = 86_400_000;
const BLOCK = "mx-[12px] mt-[12px] overflow-hidden rounded-[12px] bg-card shadow-e1";
const HEAD = "flex h-[32px] items-center justify-between px-[12px] text-[13px] font-medium hairline-b";
const ROW = "flex min-h-[29px] items-center gap-[8px] px-[12px] text-[12px] hairline-b";

export interface ServiceOrgsOptions {
  active?: boolean;
  /** `?cuec=2`: the selected CUEC; the viewer jumps to its page. */
  cuec?: number | null;
  onCuec?: (n: number | null) => void;
  onGap?: (report: SocReportOut) => void;
  onRemind?: () => void;
  /** SHL-14 for the missing CUECs (a person sends it). */
  onDraftRequest?: (reportId: string) => void;
  onSignOff?: (workpaperId: string) => void;
  /** AUD-09 row 2. */
  onInternalControl?: () => void;
  /** AUD-15, for a High exception. */
  onFindings?: (ref: string | null) => void;
  workpaperId?: string | null;
  running?: boolean;
}

const TONE: Record<ServiceOrganizationOut["status"], PillVariant> = {
  pending: "neutral",
  gap_found: "amber",
  bridge_letter_received: "green-tint",
  reliance_concluded: "green-tint",
  certification_accepted: "green-tint",
  no_reliance: "neutral",
  not_relevant: "muted",
};

function pct(on: string, from: number, span: number): number {
  return ((Date.parse(`${on}T12:00:00Z`) - from) / span) * 100;
}

function Coverage({
  report,
  onGap,
}: {
  report: SocReportOut;
  onGap?: (report: SocReportOut) => void;
}): JSX.Element | null {
  const format = useFormat();
  if (report.period_start == null || report.period_end == null) return null;
  // The plan year runs to the gap's own end (the server's); the bar only places it.
  const planEnd = report.gap.end ?? report.period_end;
  const planStart = `${planEnd.slice(0, 4)}-01-01`;
  const from = Date.parse(`${report.period_start}T12:00:00Z`);
  const to = Date.parse(`${planEnd}T12:00:00Z`);
  const span = Math.max(to - from, DAY);
  const gap = report.gap;
  const days = gap.days ?? 0;
  const socEnd = pct(report.period_end, from, span);
  const planLeft = pct(planStart, from, span);
  const label = (on: string): string => format.date(on);
  return (
    <section className={BLOCK} data-aud10="coverage">
      <div className={HEAD}>
        {COPY.coverage.title} — {report.report_type ? COPY.evaluation.type[report.report_type] : ""}
      </div>
      <div className="px-[12px] py-[10px] text-[11.5px]">
        <p className="sr-only" data-aud10="coverage-alt">
          {COPY.coverage.alt(label(report.period_start), label(report.period_end), days)}
        </p>
        <div aria-hidden="true" className="flex flex-col gap-[6px]">
          <div>
            <div className="mb-[2px] text-ink-3">{COPY.coverage.planYear}</div>
            <div className="relative h-[14px]">
              <div
                className="absolute top-0 h-[14px] rounded-[3px] bg-hair"
                style={{ left: `${planLeft}%`, right: 0 }}
              />
            </div>
          </div>
          <div>
            <div className="mb-[2px] text-ink-3">{COPY.coverage.socPeriod}</div>
            <div className="relative h-[14px]">
              <div
                className="absolute top-0 h-[14px] rounded-[3px] bg-olive"
                style={{ left: 0, width: `${socEnd}%` }}
              />
              {days > 0 && (
                <button
                  type="button"
                  data-aud10="gap"
                  data-bridged={gap.bridged ? "true" : "false"}
                  aria-label={COPY.coverage.gap(days)}
                  onClick={() => onGap?.(report)}
                  className={cn(
                    "absolute top-0 h-[14px] rounded-[3px] bg-amber-tint ring-[1px] ring-amber",
                    gap.bridged && "ring-olive",
                  )}
                  style={{
                    left: `${socEnd}%`,
                    right: 0,
                    backgroundImage:
                      "repeating-linear-gradient(135deg, var(--hair) 0 2px, transparent 2px 6px)",
                  }}
                />
              )}
            </div>
          </div>
        </div>
        {days > 0 && (
          <div
            data-aud10="gap-label"
            className={cn("mt-[6px] font-medium", gap.bridged ? "text-olive-ink" : "text-amber-ink")}
          >
            {gap.bridged ? COPY.coverage.bridged : COPY.coverage.gap(days)}
          </div>
        )}
      </div>
    </section>
  );
}

function Evaluation({ report, subservice }: {
  report: SocReportOut;
  subservice: ServiceOrganizationOut["subservice_orgs"];
}): JSX.Element {
  const format = useFormat();
  const rows: [string, string][] = [
    [COPY.evaluation.auditor, report.service_auditor_name ?? "—"],
    [COPY.evaluation.opinion, report.opinion ? COPY.evaluation.opinionWord[report.opinion] : "—"],
    [
      COPY.evaluation.typeAndPeriod,
      report.report_type && report.period_start && report.period_end
        ? `${COPY.evaluation.type[report.report_type]} · ${format.date(report.period_start)} – ${format.date(report.period_end)}`
        : "—",
    ],
    [
      COPY.evaluation.objectives,
      report.objectives_total != null
        ? COPY.evaluation.objectivesValue(report.objectives_total, report.objectives_relevant ?? 0)
        : "—",
    ],
    [
      COPY.evaluation.subservice,
      subservice.length === 0
        ? "—"
        : subservice
            .map((s) => (s.treatment === "carve_out" ? `${s.name} — ${COPY.evaluation.carveOut}` : s.name))
            .join("; "),
    ],
    [COPY.evaluation.reportDate, report.report_date ? format.date(report.report_date) : "—"],
  ];
  return (
    <section className={BLOCK} data-aud10="evaluation">
      <div className={HEAD}>{COPY.evaluation.title}</div>
      {rows.map(([key, value]) => (
        <div key={key} className={cn(ROW, "min-h-[33px]")}>
          <span className="w-[170px] shrink-0 text-ink-2">{key}</span>
          <span>{value}</span>
        </div>
      ))}
    </section>
  );
}

function Exceptions({ rows, onFindings }: {
  rows: readonly SocExceptionOut[];
  onFindings?: (ref: string | null) => void;
}): JSX.Element {
  return (
    <section className={BLOCK} data-aud10="exceptions">
      <div className={HEAD}>{COPY.exceptions.title}</div>
      {rows.map((row) => {
        const high = row.impact === "high";
        return (
          <div
            key={row.co_ref}
            data-impact={row.impact}
            className={cn("flex flex-col gap-[2px] px-[12px] py-[8px] text-[12px] hairline-b", high && "bg-red-tint")}
          >
            <span>{row.co_ref} {row.description}</span>
            <span className="text-[11.5px] text-ink-2">
              {high ? COPY.exceptions.high : COPY.exceptions.low}
              {row.impact_rationale ? `: ${row.impact_rationale}` : ""}
            </span>
            {high && onFindings !== undefined && (
              <button type="button" className="self-start text-[11.5px] font-medium text-red-ink" onClick={() => onFindings(row.routed_ref ?? null)}>
                Findings
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}

function Cuecs({ report, selected, onCuec, onInternalControl, onDraftRequest }: {
  report: SocReportOut;
  selected: number | null;
  onCuec?: (n: number | null) => void;
  onInternalControl?: () => void;
  onDraftRequest?: (reportId: string) => void;
}): JSX.Element {
  return (
    <section className={BLOCK} data-aud10="cuecs">
      <div className={HEAD}>{COPY.cuecs.title(report.cuecs_evidenced, report.cuecs.length)}</div>
      {report.cuecs.map((row: CuecOut) => (
        <button
          type="button"
          key={row.n}
          data-cuec={row.n}
          aria-pressed={selected === row.n}
          onClick={() => onCuec?.(selected === row.n ? null : row.n)}
          className={cn(
            "flex min-h-[38px] w-full items-center justify-between gap-[8px] px-[12px] text-left text-[12.5px] hairline-b",
            selected === row.n && "bg-match-bg",
          )}
        >
          <span>{row.n} {row.text}</span>
          <span className="flex items-center gap-[6px]">
            {row.status === "evidence_missing" && row.n === 2 && onInternalControl !== undefined && (
              <span
                role="link"
                tabIndex={0}
                className="text-[11.5px] text-ink-2"
                onClick={(event) => {
                  event.stopPropagation();
                  onInternalControl();
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") onInternalControl();
                }}
              >
                {COPY.cuecs.internalControl}
              </span>
            )}
            <Pill size="state" variant={row.status === "evidenced" ? "green-tint" : "red-tint"}>
              {row.status === "evidenced" ? COPY.cuecs.evidenced : COPY.cuecs.missing}
            </Pill>
          </span>
        </button>
      ))}
      {report.reliance_state === "pending" && (
        <div data-aud10="reliance" className="flex min-h-[32px] items-center justify-between gap-[8px] bg-amber-tint px-[12px] py-[4px] text-[12px] text-amber-ink">
          <span>{COPY.reliance.pending}</span>
          <Button variant="secondary" size="xs" onClick={() => onDraftRequest?.(report.id)}>
            {COPY.reliance.draftRequest}
          </Button>
        </div>
      )}
    </section>
  );
}

function Inventory({ rows }: { rows: readonly ServiceOrganizationOut[] }): JSX.Element {
  return (
    <section className={BLOCK} data-aud10="inventory">
      <div className={HEAD}>{COPY.inventory.title}</div>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-left text-ink-3">
            <th className="px-[12px] py-[4px] font-normal">{COPY.inventory.organization}</th>
            <th className="font-normal">{COPY.inventory.service}</th>
            <th className="font-normal">{COPY.inventory.relevant}</th>
            <th className="font-normal">{COPY.inventory.evidence}</th>
            <th className="font-normal">{COPY.inventory.status}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-org={row.name} className="h-[29px] hairline-t">
              <td className="px-[12px]">{row.name}</td>
              <td>{row.services}</td>
              <td>{row.relevant ? COPY.inventory.yes : COPY.inventory.no}</td>
              <td>{COPY.evidence[row.evidence_type]}</td>
              <td>
                <Pill size="state" variant={TONE[row.status]}>{COPY.status[row.status]}</Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Loading(): JSX.Element {
  return (
    <div data-aud10="drafting" className="flex flex-col gap-[12px] p-[12px]">
      <Skeleton className="h-[120px] rounded-[12px]" />
      <Skeleton className="h-[120px] rounded-[12px]" />
    </div>
  );
}

export function useServiceOrgsCanvas(
  engagementId: string,
  options: ServiceOrgsOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const active = options.active !== false && on;
  const orgs = useQuery({
    ...serviceOrgsOptions({ path: { engagement_id: engagementId } }),
    enabled: active,
    retry: false,
  });
  const items = orgs.data?.items ?? [];
  const owner = items.find((o) => o.soc_report_id != null);
  const report = useQuery({
    ...socReportOptions({
      path: { engagement_id: engagementId, soc_report_id: owner?.soc_report_id ?? "" },
    }),
    enabled: active && owner !== undefined,
    retry: false,
  });
  const running = options.running === true;
  return {
    title: COPY.title,
    actions: (
      <>
        {running && <Spinner label={COPY.title} />}
        <PaneAction label={COPY.edit} />
        <PaneAction
          label={COPY.signOff}
          onClick={() => {
            if (options.workpaperId != null) options.onSignOff?.(options.workpaperId);
          }}
        />
      </>
    ),
    children: running ? (
      <Loading />
    ) : (
      <div data-aud10="well" className="min-h-0 flex-1 overflow-y-auto bg-shell pb-[12px]">
        <Inventory rows={items} />
        {report.data !== undefined && (
          <>
            <Coverage report={report.data} {...(options.onGap === undefined ? {} : { onGap: options.onGap })} />
            <Evaluation report={report.data} subservice={owner?.subservice_orgs ?? []} />
            <Exceptions
              rows={report.data.exceptions}
              {...(options.onFindings === undefined ? {} : { onFindings: options.onFindings })}
            />
            <Cuecs
              report={report.data}
              selected={options.cuec ?? null}
              {...(options.onCuec === undefined ? {} : { onCuec: options.onCuec })}
              {...(options.onInternalControl === undefined
                ? {}
                : { onInternalControl: options.onInternalControl })}
              {...(options.onDraftRequest === undefined
                ? {}
                : { onDraftRequest: options.onDraftRequest })}
            />
          </>
        )}
      </div>
    ),
  };
}
