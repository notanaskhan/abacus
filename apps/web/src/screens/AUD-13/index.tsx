import type { AnalyticsLineOut } from "@abacus/api-client";
import {
  Amount,
  Button,
  DASH,
  Pill,
  Segmented,
  SheetModal,
  TallyPill,
  Tooltip,
  cn,
} from "@abacus/ui";
import { type JSX, type ReactNode, useId, useState } from "react";
import { BlockCard, RunRows } from "../../domain/fieldwork";
import {
  type AnalyticsNote,
  GRANITE_PEAK_ADJUSTMENTS,
  GRANITE_PEAK_ANALYTICS_RUNS,
  GRANITE_PEAK_CLIENT_ANSWER,
  GRANITE_PEAK_EXPLANATIONS,
  GRANITE_PEAK_FINAL_EXPLANATIONS,
  GRANITE_PEAK_FINAL_LINES,
  GRANITE_PEAK_LINES,
  GRANITE_PEAK_QUESTIONS,
  GRANITE_PEAK_SUBTOTALS,
  GRANITE_PEAK_UNEXPLAINED,
} from "../kit-a08-data";
import { AUD13_COPY as C } from "./copy";
import { AUD13_SCENARIOS, type Aud13Scenario, type Aud13Stage, STAGE_OF } from "./scenarios";

// AUD-13 Analytics (A-08-T28; SPEC-657; handoff AUD-13 a to e plus the Substantive tab): the T6
// statement grammar inside the T2 cockpit, in fixture mode. Whole numbers, no dollar sign,
// negatives in parentheses; an over-threshold line nobody has explained is amber, never red. The
// browser compares nothing: `over`, `status` and every figure are the server's (the seed's here).
// Ask client opens the O3 sheet with editable question cards; a person sends (DV-4). Accept is a
// manager's (SHL-10); the agent never accepts (ADR-005).

const TH = "h-[30px] bg-nested px-[8px] text-[11.5px] font-medium text-ink-3";
const TD = "px-[8px] py-[6px] text-[12px] align-top";
const GROUPS = ["income_statement", "balance_sheet"] as const;
const STAGE_LABEL: Record<Aud13Stage, (typeof C.stages)[number]> = {
  preliminary: "Preliminary",
  substantive: "Substantive",
  final: "Final",
};
const STAGE_OF_LABEL: Record<string, Aud13Stage> = {
  Preliminary: "preliminary",
  Substantive: "substantive",
  Final: "final",
};

/** The line's status for a scenario: d moves inventory to explained by the client answer. */
function statusOf(line: AnalyticsLineOut, scenario: Aud13Scenario): AnalyticsLineOut["status"] {
  if (scenario === "d" && line.fs_line_key === "inventory_net") return "explained";
  return line.status;
}

function pct(value: string | null): string {
  if (value === null) return DASH;
  return value.startsWith("-") ? `(${value.slice(1)}%)` : `${value}%`;
}

function SourceChip({ label }: { label: string }): JSX.Element {
  return (
    <span
      data-source-chip=""
      className="inline-flex h-[22px] items-center rounded-full bg-card px-[8px] text-[11.5px] text-ink-2 shadow-e1"
    >
      {label}
    </span>
  );
}

function Explanation({
  note,
  amber,
  extra,
}: {
  note: AnalyticsNote | string | undefined;
  amber?: boolean;
  extra?: ReactNode;
}): JSX.Element {
  if (note === undefined) return <span className="text-ink-3">{DASH}</span>;
  if (typeof note === "string") {
    return <span className={cn(amber === true && "text-amber-ink")}>{note}</span>;
  }
  return (
    <span className="flex flex-col gap-[4px]">
      <span>{note.text}</span>
      <span className="flex items-center gap-[6px]">
        <SourceChip label={note.source} />
        {extra}
      </span>
    </span>
  );
}

function StatusCell({
  status,
  scenario,
  line,
  onAsk,
}: {
  status: AnalyticsLineOut["status"];
  scenario: Aud13Scenario;
  line: string;
  onAsk: () => void;
}): JSX.Element {
  if (status === "within") return <span className="text-ink-3">{C.within}</span>;
  if (status === "accepted") return <Pill variant="green-tint">{C.acceptedBy("HL")}</Pill>;
  if (status === "explained") return <Pill variant="neutral">Explained</Pill>;
  const asked = scenario === "d" && line === "cost_of_goods_sold";
  return (
    <span className="flex flex-col items-start gap-[2px]">
      <Pill variant="amber">Unexplained</Pill>
      {asked ? (
        <span className="text-[11.5px] text-ink-3">{C.askedOn("Sep 14")}</span>
      ) : (
        <button type="button" className="text-[11.5px] text-ink-2 underline" onClick={onAsk}>
          {C.askClientLink}
        </button>
      )}
    </span>
  );
}

function StatementTable({
  scenario,
  stage,
  onAsk,
}: {
  scenario: Aud13Scenario;
  stage: Aud13Stage;
  onAsk: () => void;
}): JSX.Element {
  const final = stage === "final";
  const lines = final ? GRANITE_PEAK_FINAL_LINES : GRANITE_PEAK_LINES;
  const subtotals = GRANITE_PEAK_SUBTOTALS[final ? "final" : "preliminary"];
  const cols = [
    C.columns.account,
    final ? C.columns.cyAdjusted : C.columns.cy,
    C.columns.py,
    C.columns.change,
    C.columns.pct,
    final ? C.columns.adjustments : C.columns.threshold,
    C.columns.explanation,
    C.columns.status,
  ];
  const note = (l: AnalyticsLineOut): ReactNode => {
    if (final) return <Explanation note={GRANITE_PEAK_FINAL_EXPLANATIONS[l.fs_line_key]} />;
    if (scenario === "d" && l.fs_line_key === "inventory_net") {
      return (
        <Explanation
          note={GRANITE_PEAK_CLIENT_ANSWER}
          extra={
            <Button variant="tonal" size="sm">
              {C.accept}
            </Button>
          }
        />
      );
    }
    const unexplained = GRANITE_PEAK_UNEXPLAINED[l.fs_line_key];
    if (l.over && unexplained !== undefined) return <Explanation note={unexplained} amber />;
    return <Explanation note={l.over ? GRANITE_PEAK_EXPLANATIONS[l.fs_line_key] : undefined} />;
  };
  return (
    <table className="w-full border-collapse" data-aud13="statement">
      <caption className="sr-only">{final ? C.finalTitle : C.title}</caption>
      <thead>
        <tr className="hairline-b">
          {cols.map((h, i) => (
            <th
              key={h}
              scope="col"
              className={cn(TH, i === 0 || i >= 5 ? "text-left" : "text-right")}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      {GROUPS.map((group) => (
        <tbody key={group}>
          <tr>
            <th
              scope="colgroup"
              colSpan={cols.length}
              className="h-[28px] px-[8px] text-left text-[9.5px] font-medium tracking-[0.06em] text-ink-3"
            >
              {C.groups[group]}
            </th>
          </tr>
          {lines
            .filter((l) => l.group_key === group)
            .flatMap((l) => {
              const status = statusOf(l, scenario);
              const amber = l.over && status === "unexplained";
              const adjustment = GRANITE_PEAK_ADJUSTMENTS[l.fs_line_key];
              const rows: JSX.Element[] = [
                <tr
                  key={l.fs_line_key}
                  data-line={l.fs_line_key}
                  data-over={l.over ? "" : undefined}
                  data-status={status ?? undefined}
                  className={cn("hairline-b", amber && "bg-amber-tint")}
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
                  <td className={TD}>
                    {final ? (
                      <span className="text-ink-2">{adjustment?.detail ?? DASH}</span>
                    ) : (
                      <span className={cn(!l.over && "text-ink-3")}>
                        {l.over ? C.over : C.within}
                        {l.fs_line_key === "interest_expense" && (
                          <span className="block text-[11.5px] text-ink-3">{C.belowAmount}</span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className={cn(TD, "w-[290px]")}>{note(l)}</td>
                  <td className={TD}>
                    <StatusCell
                      status={status}
                      scenario={scenario}
                      line={l.fs_line_key}
                      onAsk={onAsk}
                    />
                  </td>
                </tr>,
              ];
              for (const s of subtotals.filter((t) => t.after === l.fs_line_key)) {
                rows.push(
                  <tr
                    key={s.caption}
                    data-subtotal={s.caption}
                    className={cn(
                      "font-medium",
                      s.total === true
                        ? "border-y-[3px] border-double border-stroke"
                        : "hairline-b",
                    )}
                  >
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
                    <td className={TD} colSpan={3} />
                  </tr>,
                );
              }
              return rows;
            })}
        </tbody>
      ))}
    </table>
  );
}

function Tally({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-w-[112px] flex-col gap-[4px] rounded-[10px] bg-card px-[12px] py-[8px] shadow-e1">
      <span className="text-[9.5px] font-medium tracking-[0.06em] text-ink-3 uppercase">
        {label}
      </span>
      <span className="text-[14px] tabular-nums">{children}</span>
    </div>
  );
}

function TallyStrip({ scenario, stage }: { scenario: Aud13Scenario; stage: Aud13Stage }) {
  const pending = scenario === "b";
  const explained = stage === "final" ? 8 : scenario === "d" ? 7 : 6;
  const unexplained = 8 - explained;
  const v = (n: number): ReactNode => (pending ? C.tally.pending : n);
  return (
    <div data-aud13="tallies" className="flex flex-wrap gap-[8px]">
      <Tally label={C.tally.lines}>{v(14)}</Tally>
      <Tally label={C.tally.over}>{v(8)}</Tally>
      <Tally label={C.tally.explained}>{v(explained)}</Tally>
      <Tally label={C.tally.unexplained}>
        {pending ? (
          C.tally.pending
        ) : (
          <Pill variant={unexplained > 0 ? "amber" : "muted"}>{unexplained}</Pill>
        )}
      </Tally>
      <Tally label={C.tally.threshold}>
        <Tooltip content={C.tally.thresholdTip}>
          <button type="button" data-aud13="threshold" className="text-left">
            {C.tally.thresholdValue} ⓘ
          </button>
        </Tooltip>
      </Tally>
      <Tally label={C.tally.balanced}>
        {pending ? C.tally.pending : <TallyPill code="tie" />}
      </Tally>
    </div>
  );
}

function AskClientSheet({
  open,
  onOpenChange,
  held,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  held: boolean;
}): JSX.Element {
  const id = useId();
  const [texts, setTexts] = useState(GRANITE_PEAK_QUESTIONS.map((q) => q.text));
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={C.sheet.title}
      {...(held ? { forceState: "open" as const, heldRole: "group" as const } : {})}
      action={<Button variant="primary">{C.sheet.send}</Button>}
    >
      <div data-aud13="ask-client" className="flex flex-col gap-[12px] p-[16px]">
        <p className="text-[12.5px] text-ink-2">
          {C.sheet.recipientLabel} {C.sheet.recipient} · {C.sheet.portal}
        </p>
        {GRANITE_PEAK_QUESTIONS.map((q, i) => (
          <div
            key={q.line}
            data-question={q.line}
            className="flex flex-col gap-[6px] rounded-nested bg-card p-[10px] shadow-e1"
          >
            <label htmlFor={`${id}-${q.line}`} className="text-[11.5px] text-ink-3">
              {C.sheet.questionLabel(i + 1)} · {q.movement}
            </label>
            <textarea
              id={`${id}-${q.line}`}
              value={texts[i]}
              maxLength={2000}
              onChange={(event) => {
                const next = [...texts];
                next[i] = event.target.value;
                setTexts(next);
              }}
              className="min-h-[72px] rounded-input bg-card p-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke"
            />
          </div>
        ))}
      </div>
    </SheetModal>
  );
}

export function AnalyticsWorkspace({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Aud13Scenario = (AUD13_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud13Scenario)
    : "a";
  const [stage, setStage] = useState<Aud13Stage>(STAGE_OF[scenario]);
  const [ask, setAsk] = useState(scenario === "c");
  const title =
    stage === "final" ? C.finalTitle : stage === "substantive" ? C.substantiveTitle : C.title;
  const running = scenario === "b" && stage === "preliminary";
  return (
    <div data-screen="AUD-13" data-scenario={scenario} className="bg-shell p-[12px]">
      <section aria-label={title} className="flex w-[1036px] flex-col gap-[10px]">
        <header className="flex h-[46px] items-center justify-between">
          <h1 className="text-[14.5px] font-medium">{title}</h1>
          <div className="flex gap-[6px]">
            <Button variant="ghost">{C.actions.edit}</Button>
            <Button variant="ghost">{C.actions.signOff}</Button>
            <Button variant="ghost">{C.actions.sourceDocs}</Button>
          </div>
        </header>
        <div className="flex h-[42px] items-center justify-between">
          <Segmented
            size="small"
            label={C.stageLabel}
            options={C.stages}
            active={STAGE_LABEL[stage]}
            onChange={(label) => {
              const next = STAGE_OF_LABEL[label];
              if (next !== undefined) setStage(next);
            }}
          />
          <span className="text-[12.5px] text-ink-3">{C.basis[stage]}</span>
          <Button variant="ghost">{C.actions.excel}</Button>
        </div>
        <TallyStrip scenario={scenario} stage={stage} />
        {running && (
          <RunRows
            rows={GRANITE_PEAK_ANALYTICS_RUNS.map((label, i) => ({
              id: `run-${String(i)}`,
              label,
              meta: C.runs.running,
              state: "running" as const,
            }))}
          />
        )}
        <BlockCard title={title}>
          <StatementTable
            scenario={scenario}
            stage={stage}
            onAsk={() => {
              setAsk(true);
            }}
          />
        </BlockCard>
        {stage !== "final" && (
          <footer className="flex h-[44px] items-center gap-[8px]">
            <Button
              variant="primary"
              onClick={() => {
                setAsk(true);
              }}
            >
              {C.footer.ask(scenario === "d" ? 1 : 2)}
            </Button>
            <Button variant="tonal">{C.footer.accept}</Button>
            <span className="text-[12px] text-ink-3">{C.footer.note}</span>
          </footer>
        )}
      </section>
      <AskClientSheet open={ask} onOpenChange={setAsk} held={scenario === "c"} />
    </div>
  );
}
