import type { AnalyticsLineOut } from "@abacus/api-client";
import { AgentText, Amount, Button, DASH, Pill, Segmented, cn } from "@abacus/ui";
import type { JSX } from "react";
import { BlockCard, SsarsRail, type SsarsMode } from "../../domain/fieldwork";
import {
  LAKESHORE_EXPECTATIONS,
  LAKESHORE_GRANTS_EXPLANATION,
  LAKESHORE_INQUIRIES,
  LAKESHORE_LINES,
  LAKESHORE_RUN,
  LAKESHORE_SUBTOTALS,
  SSARS_STEPS,
} from "../kit-a08-data";
import { AUD26_COPY as C } from "./copy";
import {
  AUD26_SCENARIOS,
  type Aud26Scenario,
  ENGAGEMENT_OF,
  type EngagementType,
} from "./scenarios";

// AUD-26 Review, compilation & preparation workspace (A-08-T31; SPEC-657 F9; handoff AUD-26 a to
// e) on T2 with the Agent dock, in fixture mode. The mode renders from the engagement type; review
// mode carries no risk register, sampling, confirmations or control testing (the steps leave them
// out). Statement numbers are whole, without a dollar sign. The agent's narration goes through
// AgentText and concludes nothing; Accept explanation is a person's (ADR-005).

const MODE_OF: Record<EngagementType, SsarsMode> = {
  ssars_review: "review",
  ssars_compilation: "compilation",
  ssars_preparation: "preparation",
};
const MODE_LABEL: Record<SsarsMode, (typeof C.modes)[number]> = {
  review: "Review",
  compilation: "Compilation",
  preparation: "Preparation",
};
const TH = "h-[30px] bg-nested px-[8px] text-[11.5px] font-medium text-ink-3";
const TD = "h-[34px] px-[8px] text-[12px]";

function pct(value: string | null): string {
  if (value === null) return DASH;
  return value.startsWith("-") ? `(${value.slice(1)}%)` : `${value}%`;
}

function Result({ line, unexplained }: { line: AnalyticsLineOut; unexplained: boolean }) {
  if (!line.over) return <span className="text-ink-2">{C.within}</span>;
  if (unexplained) {
    return (
      <span className="flex items-center gap-[8px]">
        <span className="font-medium text-amber-ink">{C.unexplained}</span>
        <Button variant="secondary" size="xs">
          {C.askClient}
        </Button>
      </span>
    );
  }
  return <span>{LAKESHORE_GRANTS_EXPLANATION.result}</span>;
}

function AnalyticsCanvas({ scenario }: { scenario: Aud26Scenario }): JSX.Element {
  const unexplained = scenario === "e";
  return (
    <div className="flex flex-col gap-[10px]">
      <div className="flex h-[42px] items-center justify-between">
        <Segmented size="small" label={C.viewLabel} options={C.views} active="Expectations" />
        <span className="text-[12.5px] text-ink-3">{C.threshold}</span>
      </div>
      <table className="w-full border-collapse" data-aud26="statement">
        <caption className="sr-only">{C.analyticsTitle}</caption>
        <thead>
          <tr className="hairline-b">
            {C.columns.map((h, i) => (
              <th
                key={h}
                scope="col"
                className={cn(TH, i >= 1 && i <= 4 ? "text-right" : "text-left")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        {(["revenue", "expenses"] as const).map((group) => (
          <tbody key={group}>
            <tr>
              <th
                scope="colgroup"
                colSpan={C.columns.length}
                className="h-[28px] px-[8px] text-left text-[9.5px] font-medium tracking-[0.06em] text-ink-3"
              >
                {C.groups[group]}
              </th>
            </tr>
            {LAKESHORE_LINES.filter((l) => l.group_key === group).flatMap((l) => {
              const rows = [
                <tr
                  key={l.fs_line_key}
                  data-line={l.fs_line_key}
                  data-over={l.over ? "" : undefined}
                  className={cn("hairline-b", l.over && "bg-selected")}
                >
                  <th scope="row" className={cn(TD, "text-left font-normal")}>
                    {l.caption}
                  </th>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.cy} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.py} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.change} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right tabular-nums")}>{pct(l.change_pct)}</td>
                  <td className={cn(TD, "text-ink-2")}>
                    {LAKESHORE_EXPECTATIONS[l.fs_line_key] ?? DASH}
                  </td>
                  <td className={cn(TD, l.over && "bg-amber-tint")}>
                    <Result line={l} unexplained={unexplained} />
                  </td>
                </tr>,
              ];
              for (const s of LAKESHORE_SUBTOTALS.filter((t) => t.after === l.fs_line_key)) {
                rows.push(
                  <tr key={s.caption} data-subtotal={s.caption} className="font-medium hairline-b">
                    <th scope="row" className={cn(TD, "text-left font-medium")}>
                      {s.caption}
                    </th>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={s.cy} style="whole" />
                    </td>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={s.py} style="whole" />
                    </td>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={s.change} style="whole" />
                    </td>
                    <td className={cn(TD, "text-right tabular-nums")}>{pct(s.pct)}</td>
                    <td className={cn(TD, "text-ink-3")}>
                      {s.note === undefined ? "" : C.derived}
                    </td>
                    <td className={TD}>{s.note ?? ""}</td>
                  </tr>,
                );
              }
              return rows;
            })}
          </tbody>
        ))}
      </table>
      {!unexplained && (
        <BlockCard title={C.explanationTitle}>
          <dl
            data-aud26="explanation"
            className="grid grid-cols-[120px_1fr] gap-[6px] px-[14px] py-[12px] text-[12.5px]"
          >
            <dt className="text-ink-3">{C.kv.source}</dt>
            <dd>{LAKESHORE_GRANTS_EXPLANATION.source}</dd>
            <dt className="text-ink-3">{C.kv.evidence}</dt>
            <dd>
              <span
                data-source-chip=""
                className="inline-flex h-[22px] items-center rounded-full bg-card px-[8px] text-[11.5px] shadow-e1"
              >
                {LAKESHORE_GRANTS_EXPLANATION.evidence}
              </span>
            </dd>
            <dt className="text-ink-3">{C.kv.corroborated}</dt>
            <dd>{LAKESHORE_GRANTS_EXPLANATION.corroborated}</dd>
            <dt className="text-ink-3">{C.kv.status}</dt>
            <dd className="flex items-center gap-[8px]">
              <Pill variant="green-tint">{C.explained}</Pill>
              <Button variant="secondary" size="sm">
                {C.acceptExplanation}
              </Button>
            </dd>
          </dl>
        </BlockCard>
      )}
    </div>
  );
}

function InquiriesCanvas(): JSX.Element {
  const answered = LAKESHORE_INQUIRIES.filter((q) => q.answered).length;
  return (
    <div className="flex flex-col gap-[8px]" data-aud26="inquiries">
      <div className="flex gap-[6px]">
        <Pill variant="green-tint">{C.answered(11)}</Pill>
        <Pill variant="amber">{C.open(14 - 11)}</Pill>
      </div>
      {LAKESHORE_INQUIRIES.map((q) => (
        <article
          key={q.question}
          data-inquiry={q.answered ? "answered" : "open"}
          className="flex gap-[10px] rounded-[10px] bg-card px-[14px] py-[10px] shadow-e1"
        >
          <div className="flex flex-1 flex-col gap-[3px]">
            <h3 className="text-[13px] font-medium">{q.question}</h3>
            <span className="text-[11.5px] text-ink-3">{q.respondent}</span>
            {q.answer !== undefined && <p className="text-[12.5px] text-ink-2">{q.answer}</p>}
          </div>
          <Pill variant={q.answered ? "green-tint" : "amber"}>{q.status}</Pill>
        </article>
      ))}
      <footer className="flex gap-[8px]" data-answered={answered}>
        <Button variant="secondary">{C.sendReminder}</Button>
        <Button variant="primary">{C.publish}</Button>
      </footer>
    </div>
  );
}

function PreparationPreview(): JSX.Element {
  return (
    <div className="flex flex-col gap-[12px]" data-aud26="paper-preview">
      {C.statements.map((title, i) => (
        <article
          key={title}
          data-page={i + 1}
          className="flex min-h-[220px] flex-col rounded-[6px] bg-card p-[16px] shadow-e1"
        >
          <h3 className="text-[13px] font-medium">{title}</h3>
          <span className="flex-1" />
          <footer data-page-footer="" className="flex justify-between text-[11.5px] text-ink-3">
            <span>{C.noAssurance}</span>
            <span>{C.page(i + 1, C.statements.length)}</span>
          </footer>
        </article>
      ))}
    </div>
  );
}

export function SsarsWorkspace({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Aud26Scenario = (AUD26_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud26Scenario)
    : "a";
  const engagement = ENGAGEMENT_OF[scenario];
  const mode = MODE_OF[engagement.type];
  const title =
    scenario === "b"
      ? C.inquiriesTitle
      : mode === "compilation"
        ? C.readTitle
        : mode === "preparation"
          ? C.previewTitle
          : C.analyticsTitle;
  return (
    <div
      data-screen="AUD-26"
      data-scenario={scenario}
      data-mode={mode}
      data-engagement={engagement.name}
      className="flex gap-[12px] bg-shell p-[12px]"
    >
      <SsarsRail mode={mode} steps={SSARS_STEPS[mode]} />
      <section aria-label={title} className="flex w-[696px] flex-col gap-[10px]">
        <header className="flex h-[46px] items-center justify-between">
          <h1 className="text-[14.5px] font-medium">{title}</h1>
          <div className="flex items-center gap-[8px]">
            <Segmented
              size="small"
              label={C.modeLabel}
              options={C.modes}
              active={MODE_LABEL[mode]}
            />
            <Button variant="ghost">{C.excel}</Button>
          </div>
        </header>
        {mode === "review" && scenario === "b" && <InquiriesCanvas />}
        {mode === "review" && scenario !== "b" && <AnalyticsCanvas scenario={scenario} />}
        {mode === "compilation" && (
          <BlockCard title={C.readTitle}>
            <p className="px-[14px] py-[12px] text-[12.5px] text-ink-2">{C.compilationReport}</p>
          </BlockCard>
        )}
        {mode === "preparation" && <PreparationPreview />}
      </section>
      {mode === "review" && scenario === "a" && (
        <aside aria-label={C.dock} className="flex w-[330px] flex-col gap-[8px]">
          <BlockCard title={LAKESHORE_RUN.title}>
            <div className="px-[14px] py-[10px] text-[12.5px]">
              <AgentText text={LAKESHORE_RUN.narration} />
            </div>
            <ul className="px-[14px] pb-[10px] text-[12px] text-ink-2">
              {LAKESHORE_RUN.tools.map((t) => (
                <li key={t}>✓ Execute › {t}</li>
              ))}
            </ul>
          </BlockCard>
        </aside>
      )}
    </div>
  );
}
