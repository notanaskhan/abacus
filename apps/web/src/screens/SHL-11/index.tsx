import type { DecisionCardOut, DecisionCardVersionOut } from "@abacus/api-client";
import {
  type Actor,
  Button,
  Checkbox,
  HumanAction,
  Icon,
  Pill,
  RadioGroup,
  SheetModal,
  date as formatDate,
  prose,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { useDecisionCard, useDecisionWrites, useGate } from "../../domain/review";
import { COPY } from "./copy";

// SHL-11 · Decision card (P-04-T50; P-04 §3; the handoff's SHL-11 folder): the O3 sheet at
// `?ov=decision:<cardId>`, where a judgment reserved to a role is decided. Frames built here
// (fixtures/seed/review.ts):
//
//   a  Margaret Okonkwo deciding planning materiality: the question card ("?", the reserved line),
//      context rows, two computed options with "Recommended by Accrued Agent" on the agent's,
//      the qualitative factors, the required rationale; Decide waits for an option and a rationale
//   b  Hannah Leclerc, not the reserved person: radios disabled, "Waiting on Margaret Okonkwo ·
//      requested 9:27 AM", Notify Margaret and Request more analysis…, no Decide
//   c  decided: "Decided", the decision line and the rationale as text, "View history"
//   d  the history after the Oct 6 reassessment (v1 proposed, v2 decided, v3 no change)
//   f  deficiency severity (three words, Significant deficiency recommended)
//   g  §754 recommendation (Daniel Reyes; the note that the election is Ridgeline's)
//   h  superseded: "Superseded by v3", values struck
//
// Radios are enabled only for the reserved person (the card's `decision.decide` action). Decide is
// a HumanAction that sends the option, factors, rationale and the version seen; nothing here
// decides for the agent (INV-1). The inline dock card (e) is P-04-T52's.

type Card = DecisionCardOut;

const money = (v: unknown): string | null =>
  typeof v === "string" && v !== "" ? `$${prose(v, "whole")}` : null;

/** "1.5% = $252,200 · PM $189,150 · CT $12,610" from an option's figures (server values). */
function summaryOf(card: Card, optionKey: string | null): string {
  const option = card.options.find((o) => o.key === optionKey);
  if (option === undefined) return "";
  const f = option.figures as Record<string, unknown>;
  const rate =
    typeof f.rate === "string" ? `${prose(String(Number(f.rate) * 100), "whole")}%` : null;
  const m = money(f.materiality);
  if (rate === null || m === null) return option.label;
  const pm = money(f.performance_materiality);
  const ct = money(f.clearly_trivial);
  return [
    `${option.label.split(" — ")[0] ?? rate} = ${m}`,
    ...(pm ? [`PM ${pm}`] : []),
    ...(ct ? [`CT ${ct}`] : []),
  ].join(" · ");
}

function HistoryRow({
  v,
  card,
  now,
}: {
  v: DecisionCardVersionOut;
  card: Card;
  now: Date;
}): JSX.Element {
  const at = `${formatDate(v.at, { now })}, ${time(v.at)}`;
  const f = v.figures as Record<string, unknown>;
  let text: string;
  let pill: JSX.Element;
  if (v.event === "proposed") {
    text = COPY.history.proposed(v.version_no, at);
    pill = (
      <Pill variant="amber" size="sm" className="line-through">
        {COPY.history.pills.proposed}
      </Pill>
    );
  } else if (v.event === "decided") {
    const summary = summaryOf(card, v.option_key).split(" · ")[0] ?? "";
    text = COPY.history.decided(v.version_no, v.actor_initials ?? "", at, summary);
    pill = (
      <Pill variant="green-tint" size="sm">
        {COPY.history.pills.decided}
      </Pill>
    );
  } else {
    const option = card.options.find((o) => o.key === v.option_key);
    const rate = option?.label.split(" — ")[0] ?? "";
    text = COPY.history.reassessed(
      v.version_no,
      money(f.benchmark) ?? "",
      `${rate} = ${money(f.materiality) ?? ""}`,
      money(f.difference) ?? "",
    );
    pill = (
      <Pill variant="neutral" size="sm">
        {v.changed === true ? COPY.history.pills.changed : COPY.history.pills.noChange}
      </Pill>
    );
  }
  return (
    <li
      data-history={v.event}
      className="flex min-h-[38px] items-center justify-between gap-[10px] border-b-[0.5px] border-hair px-[14px] last:border-b-0"
    >
      <span
        className={v.event === "proposed" ? "text-dense text-ink-3 line-through" : "text-dense"}
      >
        {text}
      </span>
      {pill}
    </li>
  );
}

export interface DecisionSheetProps {
  cardId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DecisionSheet({ cardId, open, onOpenChange }: DecisionSheetProps): JSX.Element {
  const query = useDecisionCard(cardId);
  const card = query.data;
  const proposed = card?.history.find((h) => h.event === "proposed");
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={card === undefined ? COPY.title("") : COPY.title(card.card.kind)}
      {...(proposed === undefined
        ? {}
        : {
            meta: (
              <span className="text-meta text-ink-3">
                {COPY.proposed(proposed.version_no, time(proposed.at))}
              </span>
            ),
          })}
    >
      {card === undefined ? (
        <p className="p-[12px] text-meta text-ink-3">
          {query.isError ? COPY.missing : COPY.loading}
        </p>
      ) : (
        <Body key={`${card.card.id}:${String(card.card.version_no)}`} card={card} />
      )}
    </SheetModal>
  );
}

function Body({ card }: { card: Card }): JSX.Element {
  const session = useSession();
  const now = useNow();
  const ids = useId();
  const head = card.card;
  const writes = useDecisionWrites(card);
  const reservedHere = head.allowed_actions.includes("decision.decide");
  const decided = card.decision;
  // The reserved person's own words, stored with the decision (never model text).
  const written = decided?.rationale ?? "";
  const superseded = head.status === "superseded";
  const [option, setOption] = useState<string | undefined>(undefined);
  const [factors, setFactors] = useState<ReadonlySet<string>>(
    new Set(card.factors.filter((f) => f.applicable && f.checked).map((f) => f.key)),
  );
  const [rationale, setRationale] = useState("");
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const role = COPY.roles[head.reserved_role] ?? head.reserved_role;
  const name = head.reserved_user_name ?? "";
  const first = name.split(" ")[0] ?? name;
  const requested = time(head.requested_at);

  const decide = useGate({
    command: () => writes.decide(option ?? "", [...factors], rationale.trim()),
    doneText: (out: Card) => COPY.toasts.decided(out.card.kind, out.card.version_no),
    failedText: COPY.toasts.failed,
  });
  const ready = option !== undefined && rationale.trim() !== "" && decide.phase !== "busy";

  return (
    <div
      className="flex flex-col gap-[12px] p-[12px]"
      data-decision={head.kind}
      data-status={head.status}
    >
      <section aria-labelledby={`${ids}-q`} className="rounded-pane bg-card shadow-e2">
        <header className="flex min-h-[44px] items-center gap-[10px] px-[14px] pt-[10px]">
          <span
            aria-hidden
            className="flex size-[19px] items-center justify-center rounded-full bg-nested text-meta font-medium text-ink-2 inset-shadow-hair"
          >
            {COPY.question}
          </span>
          <h3 id={`${ids}-q`} className="flex-1 text-section font-medium">
            {card.question}
          </h3>
          {decided !== null && !superseded && (
            <Pill variant="green" size="sm">
              {COPY.decided}
            </Pill>
          )}
          {superseded && head.superseded_by_version !== null && (
            <Pill variant="soon" size="sm">
              {COPY.superseded(head.superseded_by_version)}
            </Pill>
          )}
        </header>
        <p className="flex items-center gap-[6px] px-[14px] pb-[8px] text-meta text-ink-3">
          <Icon name="lock" size={12} />
          {COPY.reserved(role, name, head.blocking_count)}
        </p>
        {!reservedHere && decided === null && (
          <div
            role="status"
            className="mx-[14px] mb-[10px] flex items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[8px] text-dense text-amber-ink"
          >
            <Icon name="triangle-alert" size={14} />
            {COPY.waiting(name, requested)}
          </div>
        )}
        <dl className="border-t-[0.5px] border-hair">
          {card.context.map((c) => (
            <div
              key={c.key}
              className="flex min-h-[33px] items-start justify-between gap-[12px] border-b-[0.5px] border-hair px-[14px] py-[8px] last:border-b-0"
            >
              <dt className="text-dense text-ink-2">{c.label}</dt>
              <dd className="text-right text-dense">{c.value}</dd>
            </div>
          ))}
        </dl>
        {decided !== null ? (
          <div className="flex flex-col gap-[6px] border-t-[0.5px] border-hair px-[14px] py-[10px]">
            <p
              data-decision-line=""
              className={superseded ? "text-dense line-through" : "text-dense"}
            >
              {COPY.decidedLine(
                decided.decided_by_name,
                `${formatDate(decided.decided_at, { now })}, ${time(decided.decided_at)}`,
                decidedVersion(card),
                summaryOf(card, decided.option_key),
              )}
            </p>
            <p className="text-para text-ink-2">{written}</p>
          </div>
        ) : (
          <div className="border-t-[0.5px] border-hair px-[14px] py-[10px]">
            <RadioGroup
              label={card.question}
              options={card.options.map((o) => ({
                value: o.key,
                label: o.label,
                ...(reservedHere ? {} : { disabled: true }),
              }))}
              {...(option === undefined ? {} : { value: option })}
              onChange={(v) => {
                if (reservedHere) setOption(v);
              }}
            />
            <ul className="mt-[6px] flex flex-col gap-[6px]">
              {card.options.map((o) => (
                <li key={o.key} data-option={o.key} className="flex flex-col gap-[2px] pl-[26px]">
                  {o.recommended && (
                    <span className="flex items-center gap-[4px] self-start rounded-full bg-nested px-[6px] text-meta text-ink-2">
                      <Icon name="sparkles" size={12} />
                      {COPY.recommended}
                    </span>
                  )}
                  {o.detail !== null && <span className="text-dense text-ink-2">{o.detail}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {card.factors.length > 0 && decided === null && (
        <fieldset className="overflow-hidden rounded-nested bg-card shadow-e1">
          <legend className="sr-only">{COPY.factors}</legend>
          <p
            aria-hidden
            className="flex h-[33px] items-center border-b-[0.5px] border-hair px-[14px] text-section font-medium"
          >
            {COPY.factors}
          </p>
          <ul>
            {card.factors.map((f) => (
              <li
                key={f.key}
                className="flex min-h-[34px] items-center gap-[10px] px-[14px] py-[6px]"
              >
                <Checkbox
                  label={f.label}
                  showLabel
                  checked={factors.has(f.key)}
                  disabled={!reservedHere || !f.applicable}
                  onChange={(checked) => {
                    setFactors((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(f.key);
                      else next.delete(f.key);
                      return next;
                    });
                  }}
                />
                {!f.applicable && (
                  <span className="text-meta text-ink-3">{COPY.notApplicable}</span>
                )}
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      {card.note !== null && <p className="px-[4px] text-dense text-ink-2">{card.note}</p>}

      {decided === null && reservedHere && (
        <div className="flex flex-col gap-[6px]">
          <label htmlFor={`${ids}-why`} className="text-dense text-ink-2">
            {COPY.rationaleLabel}
          </label>
          <textarea
            id={`${ids}-why`}
            required
            value={rationale}
            onChange={(event) => {
              setRationale(event.target.value);
            }}
            className="h-[84px] w-full resize-none rounded-nested bg-nested p-[10px] text-body text-ink inset-shadow-hair"
          />
        </div>
      )}

      {decide.blocked !== null && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.toasts.failed}
        </p>
      )}

      <div
        data-decision="footer"
        className="sticky bottom-0 -mx-[12px] -mb-[12px] flex flex-col gap-[6px] bg-card px-[12px] pt-[10px] pb-[12px] shadow-[0_-0.5px_0_var(--color-hair)]"
      >
        {decided !== null ? (
          <div className="flex justify-start">
            <Button variant="ghost">{COPY.viewHistory}</Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-[8px]">
            <span className="flex gap-[8px]">
              {head.allowed_actions.includes("decision.notify") && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    void writes
                      .notify()
                      .then(() =>
                        toast.show({ kind: "success", text: COPY.toasts.notified(name) }),
                      );
                  }}
                >
                  {COPY.notify(first)}
                </Button>
              )}
              {head.allowed_actions.includes("decision.request_analysis") && (
                <Button
                  variant="secondary"
                  opensDialog
                  onClick={() => {
                    void writes
                      .requestAnalysis(COPY.requestPrefill)
                      .then(() => toast.show({ kind: "success", text: COPY.toasts.requested }));
                  }}
                >
                  {COPY.requestMore}
                </Button>
              )}
            </span>
            {reservedHere && (
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
          </div>
        )}
        {reservedHere && decided === null && head.kind === "planning_materiality" && (
          <p className="text-meta text-ink-3">{COPY.decideNote}</p>
        )}
      </div>

      {card.history.length > 2 && (
        <section
          aria-label={COPY.history.title}
          className="overflow-hidden rounded-nested bg-card shadow-e1"
        >
          <ol>
            {card.history.map((v) => (
              <HistoryRow key={v.version_no} v={v} card={card} now={now} />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

/** The version the decision recorded (the history's decided row). */
function decidedVersion(card: Card): number {
  return card.history.find((h) => h.event === "decided")?.version_no ?? card.card.version_no;
}
