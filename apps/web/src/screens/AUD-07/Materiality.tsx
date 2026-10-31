import type {
  BenchmarkOut,
  DecisionCardOut,
  DecisionOptionOut,
  MaterialityRecordOut,
  PlanningMaterialityVersionOut,
  ThresholdsOut,
} from "@abacus/api-client";
import { materialityCurrentOptions, materialityPreviewMutation } from "@abacus/api-client/query";
import {
  type Actor,
  AgentText,
  Button,
  type CockpitCanvas,
  HumanAction,
  Icon,
  PaneAction,
  Pill,
  Radio,
  type ViewState,
  amount,
  cn,
  date as formatDate,
  prose,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import { useDecisionCard, useDecisionWrites, useGate } from "../../domain/review";
import { DecisionInlineCard } from "../SHL-11/InlineCard";
import { COPY } from "./copy";

// AUD-07 · Materiality & partner decision (A-04-T10; A-04 §3.3, §5; docs/screens/AUD-07.md; the
// handoff spec.md and R2): the AUD-02 cockpit's Planning › Materiality canvas over the A-04 record
// (`GET …/materiality/current`) and C3's `planning_materiality` card. States: a (v1 proposed, the
// EP deciding), b (the manager: radios disabled under the banner, Remind), c (decided: the card
// collapses to one line, v1 superseded), d (reassessed at final, no change), e (revised with the
// impact list) and the C-20 states.
//
// Every figure is the server's (ADR-050). An option's thresholds are its `figures`; the slider and
// the PM/CT steppers ask `POST …/materiality/preview`, and a 409 `outside_policy` leaves the last
// figures standing: the browser never multiplies, rounds or sums. Decide is a HumanAction only for
// the card's reserved person (`decision.decide`); the agent's recommendation is a tag (INV-1).

const BLOCK = "mx-[12px] mt-[12px] overflow-hidden rounded-pane bg-card shadow-e1";
const HEAD = "flex h-[32px] items-center px-[12px] text-section font-medium hairline-b";
const SPARK_W = 48;
const SPARK_H = 16;

/** A percent the server sent ("1.5000", "75.0000") as the handoff writes it ("1.5", "75"). */
export function percentText(v: string, keepOne = false): string {
  const [whole = "0", frac = ""] = v.split(".");
  const trimmed = frac.replace(/0+$/u, "");
  if (trimmed !== "") return `${whole}.${trimmed}`;
  return keepOne ? `${whole}.0` : whole;
}

const whole = (v: string): string => amount(v, "whole").text;
const dollars = (v: string): string => prose(v, "whole");

function Block({
  title,
  right,
  children,
  name,
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  name: string;
}): JSX.Element {
  return (
    <section data-aud07={name} aria-label={title ?? name} className={BLOCK}>
      {title !== undefined && (
        <h3 className={HEAD}>
          <span className="flex-1">{title}</span>
          {right}
        </h3>
      )}
      {children}
    </section>
  );
}

// ---- the decision card (SHL-11 grammar, inline) ------------------------------------------------

function useActor(): Actor {
  const session = useSession();
  return session.user === null
    ? { kind: "system" }
    : { kind: "human", name: session.user.displayName };
}

function DecisionBlock({
  card,
  option,
  onOption,
}: {
  card: DecisionCardOut;
  option: string | undefined;
  onOption: (key: string) => void;
}): JSX.Element {
  const ids = useId();
  const now = useNow();
  const actor = useActor();
  const writes = useDecisionWrites(card);
  const head = card.card;
  const reserved = head.allowed_actions.includes("decision.decide");
  const [rationale, setRationale] = useState("");
  const name = head.reserved_user_name ?? "";
  const first = name.split(" ")[0] ?? name;
  const decide = useGate({
    command: () => writes.decide(option ?? "", [], rationale.trim()),
    doneText: () => COPY.toasts.decided,
    failedText: COPY.toasts.decided,
  });

  if (card.decision !== null) {
    // The reserved person's own words, stored with the decision (never model text).
    const written = card.decision.rationale;
    const chosen = card.options.find((o) => o.key === card.decision?.option_key);
    const when = `${formatDate(card.decision.decided_at, { now })} ${time(card.decision.decided_at)}`;
    return (
      <Block name="decision">
        <p
          data-decision-line=""
          className="flex min-h-[40px] items-center gap-[8px] px-[14px] text-body text-green-ink"
        >
          <Icon name="check" size={14} />
          {COPY.card.decidedLine(
            card.decision.decided_by_name,
            when,
            (chosen?.label ?? "").replace(" — ", " = "),
          )}
        </p>
        <p className="px-[14px] pb-[10px] text-para text-ink-2">{written}</p>
      </Block>
    );
  }

  const ready = option !== undefined && rationale.trim() !== "" && decide.phase !== "busy";
  const selected = option ?? card.recommendation?.option_key;
  return (
    <section
      data-aud07="decision"
      data-reserved={reserved ? "" : undefined}
      aria-labelledby={`${ids}-q`}
      className="mx-[12px] mt-[12px] overflow-hidden rounded-pane bg-card shadow-ask"
    >
      <header className="flex h-[40px] items-center gap-[10px] px-[14px] hairline-b">
        <span
          aria-hidden
          className="flex size-[19px] items-center justify-center rounded-full bg-nested text-meta font-medium text-ink-2"
        >
          {COPY.card.question}
        </span>
        <h3 id={`${ids}-q`} className="flex-1 text-section font-medium">
          {card.question}
        </h3>
        <span className="text-meta text-ink-3">{COPY.card.reserved}</span>
      </header>
      {!reserved && (
        <p
          role="status"
          data-aud07="banner"
          className="flex h-[32px] items-center gap-[8px] bg-amber-tint px-[14px] text-dense text-amber-ink"
        >
          <Icon name="triangle-alert" size={14} />
          {COPY.card.banner}
        </p>
      )}
      <div role="radiogroup" aria-labelledby={`${ids}-q`} className="flex flex-col">
        {card.options.map((o) => (
          <OptionRow
            key={o.key}
            o={o}
            checked={selected === o.key}
            disabled={!reserved}
            onSelect={() => {
              if (reserved) onOption(o.key);
            }}
          />
        ))}
      </div>
      {reserved && (
        <div className="px-[14px] pb-[8px]">
          <label htmlFor={`${ids}-why`} className="sr-only">
            {COPY.card.rationaleLabel}
          </label>
          <textarea
            id={`${ids}-why`}
            required
            placeholder={COPY.card.rationaleLabel}
            value={rationale}
            onChange={(event) => {
              setRationale(event.target.value);
            }}
            className="h-[64px] w-full resize-none rounded-nested bg-nested p-[10px] text-body text-ink"
          />
        </div>
      )}
      {card.context.length > 0 && (
        <ul
          aria-label={COPY.card.citations}
          className="flex flex-wrap gap-[6px] px-[14px] pb-[10px]"
        >
          {card.context.map((c) => (
            <li
              key={c.key}
              data-chip={c.key}
              className="flex h-[22px] items-center rounded-full bg-nested px-[8px] text-meta text-ink-2"
            >
              {c.label}
            </li>
          ))}
        </ul>
      )}
      <footer className="flex items-center justify-between gap-[8px] px-[14px] py-[10px] hairline-t">
        <span className="flex gap-[8px]">
          {reserved && head.allowed_actions.includes("decision.request_analysis") && (
            <Button
              variant="secondary"
              size="sm"
              opensDialog
              onClick={() => {
                void writes
                  .requestAnalysis(COPY.card.requestPrefill)
                  .then(() => toast.show({ kind: "success", text: COPY.toasts.requested }));
              }}
            >
              {COPY.card.requestMore}
            </Button>
          )}
          {!reserved && head.allowed_actions.includes("decision.notify") && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                void writes
                  .notify()
                  .then(() => toast.show({ kind: "success", text: COPY.toasts.reminded(name) }));
              }}
            >
              {COPY.card.remind(first)}
            </Button>
          )}
        </span>
        {reserved && (
          <HumanAction
            verb="Decide"
            actor={actor}
            variant="primary"
            disabled={!ready}
            loading={decide.phase === "busy"}
            onClick={() => {
              void decide.run();
            }}
          />
        )}
      </footer>
    </section>
  );
}

function OptionRow({
  o,
  checked,
  disabled,
  onSelect,
}: {
  o: DecisionOptionOut;
  checked: boolean;
  disabled: boolean;
  onSelect: () => void;
}): JSX.Element {
  return (
    <div
      data-option={o.key}
      className="flex gap-[10px] px-[14px] pt-[8px] pb-[9px]"
      {...(checked ? { "data-checked": "" } : {})}
    >
      <Radio checked={checked} label={o.label} disabled={disabled} onSelect={onSelect} />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="flex flex-wrap items-center gap-[8px] text-body">
          <span className={cn(checked && "font-medium")}>{o.label}</span>
          {o.recommended && (
            <span
              data-recommended=""
              className="flex items-center gap-[4px] rounded-full bg-nested px-[7px] text-meta text-ink-2"
            >
              <Icon name="atom" size={12} />
              {COPY.card.recommended}
            </span>
          )}
        </span>
        {o.detail !== null && <span className="text-dense text-ink-2">{o.detail}</span>}
      </span>
    </div>
  );
}

// ---- benchmarks (statement grammar: no "$") ----------------------------------------------------

/** A 3-point line of the benchmark's years, oldest first: drawing only, no figure is derived. */
function Sparkline({ b }: { b: BenchmarkOut }): JSX.Element | null {
  const series = [...b.prior_years].reverse().map((p) => Number(p.amount));
  series.push(Number(b.amount));
  if (series.length < 2) return null;
  const lo = Math.min(...series);
  const span = Math.max(...series) - lo || 1;
  const points = series
    .map((v, i) => {
      const x = (i / (series.length - 1)) * (SPARK_W - 2) + 1;
      const y = SPARK_H - 1 - ((v - lo) / span) * (SPARK_H - 2);
      return `${String(Math.round(x * 10) / 10)},${String(Math.round(y * 10) / 10)}`;
    })
    .join(" ");
  return (
    <svg
      role="img"
      aria-label={COPY.benchmarks.sparkline(b.label)}
      width={SPARK_W}
      height={SPARK_H}
      viewBox={`0 0 ${String(SPARK_W)} ${String(SPARK_H)}`}
      className="flex-none"
    >
      <polyline points={points} fill="none" stroke="var(--color-d1)" strokeWidth={1.5} />
    </svg>
  );
}

/** "2025-12-31" as the statement heading writes it, "12/31/2025". */
function slashDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return y === undefined || m === undefined || d === undefined ? "" : `${m}/${d}/${y}`;
}

function Benchmarks({ record }: { record: MaterialityRecordOut }): JSX.Element {
  const priors = record.benchmarks[0]?.prior_years.map((p) => p.year) ?? [];
  const periodEnd = record.period_end ?? "";
  const currentYear = periodEnd === "" ? "" : `PY${periodEnd.slice(0, 4)}`;
  const end = slashDate(periodEnd);
  const overall = record.benchmarks.find((b) => b.use === "overall");
  const used = (overall?.prior_years ?? [])
    .filter((p) => p.overall_used !== null && p.rate_used_pct != null)
    .map((p) =>
      COPY.benchmarks.usedPart(
        p.year,
        percentText(p.rate_used_pct ?? "", true),
        whole(p.overall_used ?? ""),
      ),
    );
  return (
    <Block name="benchmarks" title={COPY.benchmarks.title(end)}>
      <table className="w-full text-cell">
        <thead>
          <tr className="h-[28px] text-th text-ink-3 hairline-b">
            {COPY.benchmarks.columns(currentYear, priors).map((c, i) => (
              <th
                key={c}
                scope="col"
                className={cn("px-[8px] font-normal", i === 0 ? "text-left" : "text-right")}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {record.benchmarks.map((b) => (
            <tr
              key={b.key}
              data-benchmark={b.key}
              className={cn("h-[34px] hairline-b", b.use === "overall" && "font-medium")}
            >
              <th scope="row" className="px-[8px] text-left font-[inherit]">
                <span className="flex items-center gap-[6px]">
                  <span className="min-w-0 flex-1">{b.label}</span>
                  <Sparkline b={b} />
                </span>
              </th>
              <td className="px-[8px] text-right tabular-nums">{whole(b.amount)}</td>
              {b.prior_years.map((p) => (
                <td key={p.year} className="px-[8px] text-right tabular-nums text-ink-2">
                  {whole(p.amount)}
                </td>
              ))}
              <td className="px-[8px] text-right tabular-nums">
                {COPY.benchmarks.range(
                  percentText(b.range_low_pct, true),
                  percentText(b.range_high_pct, true),
                )}
              </td>
              <td className="px-[8px] text-right tabular-nums">{whole(b.low)}</td>
              <td className="px-[8px] text-right tabular-nums">{whole(b.high)}</td>
              <td className="px-[8px] text-right">{COPY.benchmarks.use[b.use] ?? b.use}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {used.length > 0 && (
        <p data-aud07="used" className="flex h-[28px] items-center px-[12px] text-meta text-ink-3">
          {COPY.benchmarks.used(used)}
        </p>
      )}
      {(record.benchmark_caption ?? []).length > 0 && (
        <p data-aud07="caption" className="px-[12px] pb-[10px] text-meta text-ink-3">
          {(record.benchmark_caption ?? []).join(" ")}
        </p>
      )}
    </Block>
  );
}

// ---- thresholds: the slider and the steppers ask the server ------------------------------------

function Stepper({
  label,
  value,
  disabled,
  onStep,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onStep: (up: boolean) => void;
}): JSX.Element {
  return (
    <span className="flex items-center gap-[2px] text-body text-ink-2">
      {`${percentText(value)}%`}
      <span className="flex flex-col">
        <button
          type="button"
          aria-label={COPY.thresholds.up(label)}
          disabled={disabled}
          onClick={() => {
            onStep(true);
          }}
          className="flex h-[9px] w-[14px] items-center justify-center text-ink-3 disabled:text-ink-4"
        >
          <Icon name="chevron-up" size={12} />
        </button>
        <button
          type="button"
          aria-label={COPY.thresholds.down(label)}
          disabled={disabled}
          onClick={() => {
            onStep(false);
          }}
          className="flex h-[9px] w-[14px] items-center justify-center text-ink-3 disabled:text-ink-4"
        >
          <Icon name="chevron-down" size={12} />
        </button>
      </span>
    </span>
  );
}

const STEP = { rate: "0.1", share: "5" } as const;

/** The next value one step up or down, as text: the control's own input, not a threshold. */
export function stepped(value: string, step: string, up: boolean): string {
  const scale = 10;
  const v = Math.round(Number(value) * scale);
  const s = Math.round(Number(step) * scale);
  const next = up ? v + s : v - s;
  return String(next / scale);
}

function ThresholdsBlock({
  shown,
  interactive,
  specificNote,
  onPreview,
  refused,
}: {
  shown: ThresholdsOut;
  interactive: boolean;
  specificNote: string | null;
  onPreview: (rate: string, pm: string, ct: string) => void;
  refused: boolean;
}): JSX.Element {
  const ids = useId();
  const low = shown.policy_low_pct;
  const high = shown.policy_high_pct;
  return (
    <Block name="thresholds">
      <div className="flex h-[44px] items-center gap-[10px] px-[12px] hairline-b">
        <span className="text-meta text-ink-3">{`${percentText(low, true)}%`}</span>
        <label htmlFor={`${ids}-rate`} className="sr-only">
          {COPY.thresholds.rate}
        </label>
        <input
          id={`${ids}-rate`}
          type="range"
          data-aud07="slider"
          min={low}
          max={high}
          step={STEP.rate}
          value={shown.rate_pct}
          disabled={!interactive}
          aria-valuetext={`${percentText(shown.rate_pct, true)}%`}
          onChange={(event) => {
            onPreview(event.target.value, shown.pm_pct, shown.ct_pct);
          }}
          className="h-[16px] flex-1 accent-cta-deep"
        />
        <span className="text-meta text-ink-3">{`${percentText(high, true)}%`}</span>
      </div>
      <dl>
        <Row label={COPY.thresholds.overall}>
          <span data-figure="overall" className="tabular-nums">
            {dollars(shown.overall)}
          </span>
        </Row>
        <Row label={COPY.thresholds.pm}>
          <Stepper
            label={COPY.thresholds.pm}
            value={shown.pm_pct}
            disabled={!interactive}
            onStep={(up) => {
              onPreview(shown.rate_pct, stepped(shown.pm_pct, STEP.share, up), shown.ct_pct);
            }}
          />
          <span data-figure="pm" className="tabular-nums">
            {dollars(shown.pm)}
          </span>
        </Row>
        <Row label={COPY.thresholds.ct}>
          <Stepper
            label={COPY.thresholds.ct}
            value={shown.ct_pct}
            disabled={!interactive}
            onStep={(up) => {
              onPreview(shown.rate_pct, shown.pm_pct, stepped(shown.ct_pct, STEP.share, up));
            }}
          />
          <span data-figure="ct" className="tabular-nums">
            {dollars(shown.ct)}
          </span>
        </Row>
        <Row label={COPY.thresholds.specific}>
          <span className="flex flex-col items-end">
            <span className="text-ink-2">{COPY.thresholds.none}</span>
            {specificNote !== null && <span className="text-meta text-ink-3">{specificNote}</span>}
          </span>
        </Row>
      </dl>
      {refused && (
        <p role="alert" className="px-[12px] pb-[8px] text-meta text-red-ink">
          {COPY.thresholds.outside}
        </p>
      )}
    </Block>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center gap-[10px] px-[12px] py-[4px] text-body hairline-b last:shadow-none">
      <dt className="flex-1">{label}</dt>
      <dd className="flex items-center gap-[12px]">{children}</dd>
    </div>
  );
}

// ---- factors, reassessment, impact, history ----------------------------------------------------

function Factors({ record }: { record: MaterialityRecordOut }): JSX.Element {
  return (
    <Block name="factors" title={COPY.factors.title}>
      <ul>
        {record.qualitative_factors.map((f) => (
          <li
            key={f.text}
            data-applies={f.applies ? "" : undefined}
            className="flex min-h-[32px] items-center gap-[10px] px-[12px] text-body hairline-b"
          >
            <span
              role="img"
              aria-label={f.applies ? COPY.factors.applies : COPY.factors.notApplies}
              className={cn(
                "flex size-[15px] flex-none items-center justify-center rounded-full",
                f.applies ? "bg-green text-on-dark" : "inset-ring-[1.3px] inset-ring-ink-3",
              )}
            >
              {f.applies && <Icon name="check" size={12} />}
            </span>
            <span className={cn("flex-1", !f.applies && "text-ink-2")}>{f.text}</span>
          </li>
        ))}
      </ul>
    </Block>
  );
}

function Reassessment({
  version,
  stands,
}: {
  version: PlanningMaterialityVersionOut;
  stands: PlanningMaterialityVersionOut | undefined;
}): JSX.Element | null {
  const r = version.reassessment;
  if (r === null) return null;
  const base = stands?.version_no ?? version.version_no - 1;
  const rate = percentText(version.thresholds.rate_pct, true);
  return (
    <Block
      name="reassessment"
      title={COPY.reassessment.title}
      {...(version.status === "revised"
        ? {
            right: (
              <Pill variant="amber" size="sm">
                {COPY.status.revised}
              </Pill>
            ),
          }
        : {})}
    >
      <dl>
        <Row label={COPY.reassessment.finalAmount}>
          <span className="tabular-nums">{whole(r.final_amount)}</span>
        </Row>
        <Row label={COPY.reassessment.atRate(rate)}>
          <span className="tabular-nums">{dollars(r.at_rate)}</span>
        </Row>
        <Row label={COPY.reassessment.difference(base)}>
          <span className="tabular-nums">{`${dollars(r.difference)} (${r.difference_pct}%)`}</span>
        </Row>
        <Row label={COPY.reassessment.conclusion}>
          <span data-aud07="conclusion" className="max-w-[420px] text-right">
            {r.conclusion === "revised"
              ? COPY.reassessment.revised
              : COPY.reassessment.noChange(
                  base,
                  dollars(stands?.thresholds.pm ?? version.thresholds.pm),
                )}
          </span>
        </Row>
      </dl>
      {version.impact.length > 0 && (
        <section aria-label={COPY.impact.title} data-aud07="impact">
          <p className="flex h-[30px] items-center px-[12px] text-th font-medium text-ink-2">
            {COPY.impact.title}
          </p>
          <ul>
            {version.impact.map((i) => (
              <li
                key={i.workpaper_code}
                className="flex min-h-[32px] items-center gap-[10px] px-[12px] text-body hairline-b"
              >
                <span className="w-[64px] text-ink-2">{i.workpaper_code}</span>
                <span className="flex-1">{i.title}</span>
                <span className="text-meta text-ink-3">{COPY.impact.reasons[i.reason]}</span>
                {i.preparer_name !== null && (
                  <span className="text-meta text-ink-2">{i.preparer_name}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </Block>
  );
}

const statusWord = (v: PlanningMaterialityVersionOut): string =>
  v.superseded ? COPY.status.superseded : COPY.status[v.status];

function History({ record }: { record: MaterialityRecordOut }): JSX.Element {
  const now = useNow();
  return (
    <Block name="history" title={COPY.history.title}>
      <ol>
        {record.versions.map((v) => {
          const sameDay = formatDate(v.created_at, { now }) === formatDate(now, { now });
          const when =
            v.status === "reassessed" || v.status === "revised"
              ? formatDate(v.created_at, { now })
              : sameDay && v.version_no > 1
                ? time(v.created_at)
                : `${formatDate(v.created_at, { now })} ${time(v.created_at)}`;
          const tail =
            v.status === "proposed"
              ? COPY.history.recommended(percentText(v.thresholds.rate_pct, true))
              : v.status === "decided"
                ? COPY.history.shares(dollars(v.thresholds.pm), dollars(v.thresholds.ct))
                : v.status === "reassessed"
                  ? COPY.history.noChange
                  : COPY.history.revised;
          return (
            <li
              key={v.version_no}
              data-version={v.version_no}
              data-status={v.superseded ? "superseded" : v.status}
              className="flex min-h-[38px] items-center gap-[10px] px-[12px] text-body hairline-b"
            >
              <span className={cn("flex-1", v.superseded && "text-ink-2")}>
                {[
                  COPY.version(v.version_no, COPY.status[v.status]),
                  v.created_by_name,
                  when,
                  tail,
                ].join(" · ")}
              </span>
              {v.current && (
                <Pill variant="neutral" size="sm">
                  {COPY.status.current}
                </Pill>
              )}
              {v.superseded && (
                <Pill variant="soon" size="sm">
                  {statusWord(v)}
                </Pill>
              )}
            </li>
          );
        })}
      </ol>
    </Block>
  );
}

// ---- the canvas --------------------------------------------------------------------------------

export interface MaterialityOptions {
  /** The canvas is on screen: the reads run only then (the cockpit calls the hook always). */
  active?: boolean;
}

function useRecord(engagementId: string, enabled: boolean) {
  return useQuery({
    ...materialityCurrentOptions({ path: { engagement_id: engagementId } }),
    enabled,
  });
}

/** AUD-07's canvas for the cockpit (AUD-02 renders it for `?section=materiality`). */
export function useMaterialityCanvas(
  engagementId: string,
  options: MaterialityOptions = {},
): CockpitCanvas {
  const on = useFlag("assurance.materiality") === true;
  const active = options.active ?? true;
  const record = useRecord(engagementId, on && active);
  const data = record.data;
  const cardId = data?.pending_card_id ?? data?.current?.decision_card_id ?? "";
  const card = useDecisionCard(cardId);
  const [option, setOption] = useState<string | undefined>(undefined);
  const [previewed, setPreviewed] = useState<ThresholdsOut | null>(null);
  const [refused, setRefused] = useState(false);
  const preview = useMutation(materialityPreviewMutation());

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "assurance.materiality" };
  else if (record.isError) {
    const status = (record.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void record.refetch() };
  } else if (data === undefined) state = { kind: "loading" };
  else if (data.current === null) state = { kind: "empty" };

  const c = card.data;
  const reserved =
    c?.card.allowed_actions.includes("decision.decide") === true && c.decision === null;
  const picked = c?.options.find((o) => o.key === (option ?? c.recommendation?.option_key));
  const fromOption = (o: DecisionOptionOut | undefined): ThresholdsOut | null => {
    const base = data?.current?.thresholds;
    const f = o?.figures as Record<string, string> | undefined;
    if (base === undefined || f?.overall === undefined) return null;
    return {
      ...base,
      rate_pct: f.rate_pct ?? base.rate_pct,
      overall: f.overall,
      pm_pct: f.pm_pct ?? base.pm_pct,
      pm: f.pm ?? base.pm,
      ct_pct: f.ct_pct ?? base.ct_pct,
      ct: f.ct ?? base.ct,
    };
  };
  const shown: ThresholdsOut | undefined =
    (option === "custom" || previewed !== null ? previewed : null) ??
    (c?.decision === null ? fromOption(picked) : null) ??
    data?.current?.thresholds;

  const ask = (rate: string, pm: string, ct: string): void => {
    if (!reserved || shown === undefined) return;
    if (option !== "custom") setOption("custom");
    preview.mutate(
      {
        path: { engagement_id: engagementId },
        body: {
          basis: shown.basis,
          benchmark_key: shown.benchmark_key,
          rate_pct: rate,
          pm_pct: pm,
          ct_pct: ct,
        },
      },
      {
        onSuccess: (out) => {
          setRefused(false);
          setPreviewed(out);
        },
        onError: () => {
          setRefused(true);
        },
      },
    );
  };

  const current = data?.current ?? null;
  const decidedVersion = data?.versions.find((v) => v.status === "decided" && !v.superseded);
  return {
    title: COPY.title,
    well: true,
    state,
    empty: { title: COPY.states.empty },
    actions: (
      <>
        {current !== null && (
          <Pill variant={current.status === "decided" ? "green-tint" : "amber"} size="sm">
            {COPY.version(current.version_no, COPY.status[current.status])}
          </Pill>
        )}
        <PaneAction icon="pencil" label={COPY.actions.edit} />
        <PaneAction icon="file" label={COPY.actions.sourceDocs} />
        <PaneAction icon="check" label={COPY.actions.signOff} disabled />
      </>
    ),
    children:
      data === undefined || current === null ? null : (
        <div data-aud07="body" className="flex flex-col pb-[12px]">
          {c !== undefined && (
            <DecisionBlock
              card={c}
              option={option}
              onOption={(key) => {
                setOption(key);
                setPreviewed(null);
                setRefused(false);
              }}
            />
          )}
          {current.reassessment !== null && (
            <Reassessment version={current} stands={decidedVersion} />
          )}
          <Benchmarks record={data} />
          {shown !== undefined && (
            <ThresholdsBlock
              shown={shown}
              interactive={reserved}
              specificNote={data.specific_note ?? null}
              onPreview={ask}
              refused={refused}
            />
          )}
          <Factors record={data} />
          <History record={data} />
        </div>
      ),
  };
}

// ---- the dock: the recommender's reasons and the SHL-11 e card --------------------------------

export function MaterialityDock({ engagementId }: { engagementId: string }): JSX.Element | null {
  const record = useRecord(engagementId, useFlag("assurance.materiality") === true);
  const cardId = record.data?.pending_card_id ?? record.data?.current?.decision_card_id ?? "";
  const card = useDecisionCard(cardId);
  const c = card.data;
  if (c === undefined) return null;
  const who = c.card.reserved_user_name ?? "";
  return (
    <div data-aud07="dock" className="flex flex-col gap-[10px] p-[10px]">
      {c.decision === null ? (
        <p className="flex h-[32px] items-center rounded-nested bg-amber-tint px-[10px] text-dense text-amber-ink">
          {COPY.dock.waiting(who, time(c.card.requested_at))}
        </p>
      ) : (
        <p className="text-dense text-ink-2">{COPY.dock.decided(c.decision.decided_by_name)}</p>
      )}
      {c.decision === null &&
        (c.recommendation?.reasons ?? []).map((r) => (
          <AgentText key={r} text={r} className="rounded-pane bg-card p-[10px] shadow-e1" />
        ))}
      <DecisionInlineCard cardId={c.card.id} variant="dock" />
    </div>
  );
}
