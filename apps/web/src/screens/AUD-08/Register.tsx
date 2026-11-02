import type { RegisterOut, RegisterRiskOut } from "@abacus/api-client";
import { riskLinkageOptions, riskRegisterOptions } from "@abacus/api-client/query";
import {
  PaneAction,
  Pill,
  Segmented,
  ViewStateBody,
  type ViewState,
  cn,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { AuditBar, isNotFound, useAuditCockpit } from "../../domain/audits";
import { COPY } from "./copy";

// AUD-08 · Risk assessment register (A-04-T20; A-04 §3 AC4; the handoff spec and R2 revision): the
// T6 workbook over `GET …/risks/register` (A-04-T13) and `…/risks/linkage`: the control row, the
// tally strip from the server's tally (never recounted here), and the statement-grammar grid with
// rating chips and status pills (no "$"). A row opens the O2 rationale drawer (`?ov=risk:<code>`);
// the UNADDRESSED card filters to the unaddressed rows (`?filter=unaddressed`). States a, b, b2 and
// d (A-04-T29 builds c, e, f, g).

const CARD = "flex h-[40px] flex-1 flex-col justify-center rounded-[10px] bg-card px-[10px] shadow-e1";
const LABEL = "text-micro font-medium uppercase tracking-[.07em] text-ink-3";
const COLS =
  "grid grid-cols-[34px_196px_150px_64px_52px_64px_84px_104px_1fr_74px] items-center gap-[6px]";

const CHIP: Record<string, string> = {
  low: "neutral",
  moderate: "amber",
  high: "red-tint",
  max: "neutral",
};

function Rating({ value }: { value: string }): JSX.Element {
  return (
    <Pill variant={(CHIP[value] ?? "neutral") as "neutral"} size="micro" data-rating={value}>
      {COPY.rating[value] ?? value}
    </Pill>
  );
}

function Tally({
  data,
  filtered,
  onFilter,
}: {
  data: RegisterOut;
  filtered: boolean;
  onFilter: (on: boolean) => void;
}): JSX.Element {
  const t = data.tally;
  return (
    <div data-aud08="tally" className="flex h-[52px] items-center gap-[8px] px-[12px]">
      <div className={CARD} data-tally="risks">
        <span className={LABEL}>{COPY.tally.risks}</span>
        <span className="text-[15px]">{t.risks}</span>
      </div>
      <div className={CARD} data-tally="significant">
        <span className={LABEL}>{COPY.tally.significant}</span>
        <span className="flex items-center gap-[6px] text-[15px]">
          {t.significant}
          {t.significant_proposed > 0 && (
            <Pill variant="amber" size="micro">
              {COPY.proposed(t.significant_proposed)}
            </Pill>
          )}
        </span>
      </div>
      <div className={CARD} data-tally="fraud">
        <span className={LABEL}>{COPY.tally.fraud}</span>
        <span className="flex items-center gap-[6px] text-[15px]">
          {t.fraud}
          {t.fraud > 0 && (
            <Pill variant="red-tint" size="micro">
              {COPY.presumed}
            </Pill>
          )}
        </span>
      </div>
      <div className={CARD} data-tally="high_rmm">
        <span className={LABEL}>{COPY.tally.highRmm}</span>
        <span className="text-[15px]">{t.high_rmm}</span>
      </div>
      <button
        type="button"
        data-tally="unaddressed"
        aria-pressed={filtered}
        className={cn(CARD, "text-left", filtered && "inset-shadow-hair")}
        onClick={() => {
          onFilter(!filtered);
        }}
      >
        <span className={LABEL}>{COPY.tally.unaddressed}</span>
        <span className="flex items-center gap-[6px] text-[15px]">
          {t.unaddressed}
          {t.unaddressed > 0 && (
            <Pill variant="amber" size="tally">
              {`off ${String(t.unaddressed)}`}
            </Pill>
          )}
        </span>
      </button>
      <div className={CARD} data-tally="ep_approval">
        <span className={LABEL}>{COPY.tally.epApproval}</span>
        <span>
          <Pill variant={t.ep_approval === "approved" ? "green-tint" : "muted"} size="micro">
            {t.ep_approval === "approved" ? COPY.approved : COPY.pending}
          </Pill>
        </span>
      </div>
    </div>
  );
}

function RiskRow({
  risk,
  response,
  onOpen,
}: {
  risk: RegisterRiskOut;
  response: string | undefined;
  onOpen: (code: string) => void;
}): JSX.Element {
  const assertions =
    risk.level === "financial_statement"
      ? COPY.all
      : risk.assertions.map((a) => COPY.assertion[a] ?? a).join(" · ");
  const significance = risk.significance === "none" ? null : COPY.significance[risk.significance];
  const fraud = risk.fraud === "none" ? null : COPY.fraud[risk.fraud];
  return (
    <button
      type="button"
      data-risk={risk.code}
      data-unaddressed={risk.unaddressed ? "true" : "false"}
      className={cn(COLS, "h-[34px] w-full px-[10px] text-left text-body hairline-b hover:bg-tonal-hover")}
      onClick={() => {
        onOpen(risk.code);
      }}
    >
      <span className="text-ink-3">{risk.code}</span>
      <span className="truncate">{risk.area_label}</span>
      <span className="truncate text-ink-2">{assertions}</span>
      <Rating value={risk.inherent_risk} />
      <Rating value={risk.control_risk} />
      <Rating value={risk.rmm} />
      <span>
        {significance !== null && (
          <Pill
            variant={risk.significance === "approved" ? "green-tint" : risk.significance === "proposed" ? "amber" : "neutral"}
            size="micro"
          >
            {significance}
          </Pill>
        )}
      </span>
      <span>
        {fraud !== null && (
          <Pill
            variant={risk.fraud === "presumed" ? "red-tint" : risk.fraud === "rebuttal_approved" ? "green-tint" : "amber"}
            size="micro"
          >
            {fraud}
          </Pill>
        )}
      </span>
      <span
        className={cn(
          "truncate",
          risk.unaddressed && "rounded-[5px] bg-red-tint px-[6px] font-medium text-red-ink",
        )}
      >
        {risk.unaddressed ? COPY.unaddressed : (response ?? "")}
      </span>
      <span>
        <Pill variant={risk.status === "ep_approved" ? "green-tint" : "neutral"} size="micro">
          {COPY.status[risk.status] ?? risk.status}
        </Pill>
      </span>
    </button>
  );
}

export function RiskRegisterPage({
  auditId,
  filter,
  onFilter,
  onRisk,
  onBack,
}: {
  auditId: string;
  filter: "unaddressed" | null;
  onFilter: (filter: "unaddressed" | null) => void;
  onRisk: (code: string) => void;
  onBack?: () => void;
}): JSX.Element {
  const on = useFlag("assurance.risk_register") === true;
  const cockpit = useAuditCockpit(auditId);
  const engagementId = cockpit.data?.engagement_id;
  const path = { path: { engagement_id: engagementId ?? "" } };
  const register = useQuery({ ...riskRegisterOptions(path), enabled: on && engagementId !== undefined });
  const linkage = useQuery({ ...riskLinkageOptions(path), enabled: on && engagementId !== undefined });
  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "assurance.risk_register" };
  else if (cockpit.isError || register.isError) {
    const error = cockpit.error ?? register.error;
    state = isNotFound(error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void register.refetch() };
  } else if (register.data === undefined) state = { kind: "loading" };

  const responses = new Map<string, string>();
  for (const cell of linkage.data?.cells ?? []) {
    if (cell.state !== "linked" || responses.has(cell.risk_code)) continue;
    const target = linkage.data?.targets.find((t) => t.ref === cell.target_ref);
    if (target !== undefined) responses.set(cell.risk_code, target.label);
  }
  const data = register.data;
  const rows = (data?.risks ?? []).filter((r) => filter !== "unaddressed" || r.unaddressed);
  const groups = (["financial_statement", "assertion"] as const)
    .map((level) => ({ level, rows: rows.filter((r) => r.level === level) }))
    .filter((g) => g.rows.length > 0);
  return (
    <div data-screen="AUD-08" className="flex min-h-0 flex-1 flex-col">
      {cockpit.data !== undefined && (
        <AuditBar cockpit={cockpit.data} {...(onBack === undefined ? {} : { onBack })} />
      )}
      <ViewStateBody state={state} empty={{ title: COPY.title }}>
        {data !== undefined && (
          <div className="flex min-h-0 flex-1 flex-col">
            <header className="flex h-[46px] items-center gap-[8px] px-[12px]">
              <h2 className="text-[14.5px] font-medium">{COPY.title}</h2>
              <span className="flex-1" />
              <PaneAction icon="pencil" label={COPY.edit} />
              <PaneAction label={COPY.signOff} />
            </header>
            <div className="flex h-[42px] items-center gap-[8px] px-[12px]">
              <Segmented size="small" label={COPY.title} options={COPY.tabs} active={COPY.tabs[0]} />
              <span className="flex-1" />
              <PaneAction icon="file-spreadsheet" label={COPY.openExcel} />
            </div>
            <Tally
              data={data}
              filtered={filter === "unaddressed"}
              onFilter={(f) => {
                onFilter(f ? "unaddressed" : null);
              }}
            />
            <div
              role="table"
              aria-label={COPY.title}
              className="mx-[12px] mb-[12px] overflow-hidden rounded-pane bg-card shadow-e1"
            >
              <div
                role="row"
                className={cn(COLS, "h-[30px] bg-nested px-[10px] text-[11.5px] font-medium text-ink-2")}
              >
                {Object.values(COPY.columns).map((c) => (
                  <span key={c} className="truncate">
                    {c}
                  </span>
                ))}
              </div>
              {groups.map((g) => (
                <div key={g.level} data-group={g.level}>
                  <div className="flex h-[24px] items-center px-[10px] text-[10px] font-medium uppercase text-ink-3">
                    {COPY.groups[g.level]}
                  </div>
                  {g.rows.map((r) => (
                    <RiskRow key={r.id} risk={r} response={responses.get(r.code)} onOpen={onRisk} />
                  ))}
                </div>
              ))}
              <p className="flex h-[30px] items-center px-[10px] text-[11px] text-ink-3">
                {COPY.standBack}
              </p>
            </div>
          </div>
        )}
      </ViewStateBody>
    </div>
  );
}
