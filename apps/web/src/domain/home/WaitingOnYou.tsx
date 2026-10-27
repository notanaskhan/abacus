// "Waiting on you" (HOME-01 F2; I-01-T06): the summary line, then the bands in DF-25 order, each
// with its count from the one counts response, then rows of 44: the glyph chip, the title, the
// context (amber with words when blocked), the due chip and a chevron. A row opens where its gate
// is decided; it never decides (INV-1: no row renders a gate verb), so a row is a link or, while
// its target is planned, plain text.

import type { HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import { AgentText, Icon, Pill, cn, date } from "@abacus/ui";
import type { JSX } from "react";
import { type Band, dueChip, glyphOf, summaryParts, visibleBands } from "./gateClasses";
import { HOME_MESSAGES } from "./messages";

export interface WaitingOnYouProps {
  counts: HumanGateCountsOut;
  gates: readonly HumanGateOut[];
  /** The firm's today (ISO date), for the due chips. */
  today: string;
  now: Date;
  tz?: string;
  /** Where a row goes, or undefined while its target is planned. */
  hrefOf?: (gate: HumanGateOut) => string | undefined;
}

/** A registered gate name read as words when the owner's resolver has not titled the row yet
 * ("acceptance_decision_due" → "Acceptance decision due"). */
function fallbackTitle(subkind: string): string {
  const words = subkind.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function byDeadline(a: HumanGateOut, b: HumanGateOut): number {
  if (a.due_on !== b.due_on) {
    if (a.due_on === null) return 1;
    if (b.due_on === null) return -1;
    return a.due_on < b.due_on ? -1 : 1;
  }
  return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
}

function Row({
  gate,
  today,
  now,
  tz,
  href,
}: {
  gate: HumanGateOut;
  today: string;
  now: Date;
  tz: string | undefined;
  href: string | undefined;
}): JSX.Element {
  const title = gate.title ?? fallbackTitle(gate.subkind);
  const chip =
    gate.due_on === null
      ? null
      : dueChip(today, gate.due_on, (iso) =>
          date(iso, { now, ...(tz === undefined ? {} : { tz }) }),
        );
  const body = (
    <>
      <span
        aria-hidden="true"
        className={cn(
          "inline-flex size-[22px] shrink-0 items-center justify-center rounded-full bg-nested",
          gate.blocked ? "text-amber-ink" : "text-ink-2",
        )}
      >
        <Icon name={glyphOf(gate)} size={12} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        {/* Titles and context lines come from the owners' resolvers and may quote an agent's
            words (I-01-T07): rendered through AgentText, never raw (frontend rule 2). */}
        <AgentText
          inline
          text={title}
          className="truncate text-body leading-[1.3] font-medium text-ink"
        />
        {(gate.context != null || gate.blocked) && (
          <span
            className={cn(
              "truncate text-meta leading-[1.35]",
              gate.blocked ? "text-amber-ink" : "text-ink-3",
            )}
          >
            {gate.blocked && <span className="sr-only">{`${HOME_MESSAGES.blocked}: `}</span>}
            {gate.context == null ? (
              HOME_MESSAGES.blocked
            ) : (
              <AgentText
                inline
                text={gate.context}
                className="text-meta leading-[1.35] text-inherit"
              />
            )}
          </span>
        )}
      </span>
      {chip !== null && (
        <Pill variant={chip.variant} size="state" className="shrink-0" data-risk={chip.risk}>
          {chip.label}
        </Pill>
      )}
      <Icon name="chevron-right" size={13} className="shrink-0 text-ink-3" />
    </>
  );
  const row = "flex min-h-[44px] items-center gap-[12px] py-[5px] pr-[12px] pl-[14px] hairline-b";
  return (
    <li data-gate={gate.id} data-band={gate.band}>
      {href === undefined ? (
        <div className={row}>{body}</div>
      ) : (
        <a href={href} className={cn(row, "hover:bg-shell")}>
          {body}
        </a>
      )}
    </li>
  );
}

function BandHeader({ band, n }: { band: Band; n: number }): JSX.Element {
  return (
    <h3
      data-band-header={band}
      className="-mt-[0.5px] flex h-[31px] items-center gap-[8px] bg-band-hd px-[14px] text-body font-medium hairline-t hairline-b"
    >
      <span className="min-w-0 flex-1 truncate">{HOME_MESSAGES.bands[band]}</span>
      <span className="text-dense font-normal text-ink-3 tabular-nums">{n}</span>
    </h3>
  );
}

export function WaitingOnYou({
  counts,
  gates,
  today,
  now,
  tz,
  hrefOf,
}: WaitingOnYouProps): JSX.Element {
  const bands = visibleBands(counts.bands);
  return (
    <div data-home="waiting" className="flex flex-col">
      <p
        data-home="summary"
        className="flex h-[36px] flex-none items-center px-[14px] text-dense text-ink-3 hairline-b"
      >
        {[...summaryParts(counts.bands), HOME_MESSAGES.sortedBy].join(" · ")}
      </p>
      {bands.map((band) => {
        const rows = gates.filter((g) => g.band === band).sort(byDeadline);
        return (
          <section key={band} aria-label={HOME_MESSAGES.bands[band]}>
            <BandHeader band={band} n={counts.bands[band]} />
            {rows.length > 0 && (
              <ul>
                {rows.map((gate) => (
                  <Row
                    key={gate.id}
                    gate={gate}
                    today={today}
                    now={now}
                    tz={tz}
                    href={hrefOf?.(gate)}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
