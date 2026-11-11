// TAX-07 · Return › Activity and Checkpoints (T-04-T27; handoff TAX-07) in fixture mode on the T2
// single-pane variant (1006 + 360). The Timeline: 76px right-aligned date column, 20px markers on
// a hairline (dark disc with a check for approvals, ink-3 disc with an x for reversals, line
// glyphs for neutral events), "{Verb} by {Actor}" titles. Every approval names a person; the
// agent only proposes and self-checks. A checkpoint row opens SHL-16 (the host); Restore… makes a
// new checkpoint there, never a rewrite. The kind filter and the live search narrow the rows.
import { Button, Pill } from "@abacus/ui";
import { type JSX, useMemo, useState } from "react";
import {
  CHECKPOINTS,
  type Checkpoint,
  COPY,
  DELIVERED,
  EVENTS,
  type Event,
  FILTERS,
  type Frame,
  type Kind,
  PROPOSED_CHECKPOINT,
  PROPOSED_DIFF,
  PROPOSED_EVENT,
} from "./copy";

export interface ActivityProps {
  frame: Frame;
  /** A checkpoint row: SHL-16 diff drawer. */
  onOpenCheckpoint?: (key: string) => void;
  /** Compare…: SHL-16 with two pickers. */
  onCompare?: () => void;
  /** Star toggles a named checkpoint (the host posts; the frame answers). */
  onStar?: (key: string) => void;
  /** A row that names a screen: SHL-08, INB-01, TXP-12, TAX-09, SIG-01 or TAX-12. */
  onOpenLink?: (link: NonNullable<Event["link"]>) => void;
}

const GLYPH: Record<Event["marker"], string> = {
  check: "✓",
  reverse: "×",
  mail: "✉",
  upload: "⤒",
  download: "⤓",
  send: "➤",
  file: "▤",
  plus: "+",
  help: "?",
  atom: "⚛",
};

function Marker({ marker }: { marker: Event["marker"] }): JSX.Element {
  const disc = marker === "check" || marker === "reverse";
  return (
    <span
      aria-hidden
      data-marker={marker}
      className={`z-10 flex size-[20px] shrink-0 items-center justify-center rounded-full text-[11px] ${disc ? (marker === "check" ? "bg-espresso text-on-dark" : "bg-ink-3 text-on-dark") : "bg-card text-ink-2"}`}
    >
      {GLYPH[marker]}
    </span>
  );
}

function Row({
  event,
  onOpenLink,
}: {
  event: Event;
  onOpenLink?: ActivityProps["onOpenLink"];
}): JSX.Element {
  const body = (
    <>
      <span className="flex w-[76px] shrink-0 flex-col items-end">
        <span className="text-[12.5px] text-ink-2">{event.date}</span>
        <span className="text-[11.5px] text-ink-3">{event.time}</span>
      </span>
      <Marker marker={event.marker} />
      <span className="flex min-w-0 flex-col">
        <span className="text-[13.5px] font-medium">{event.title}</span>
        {event.sub ? <span className="text-[12.5px] text-ink-2">{event.sub}</span> : null}
      </span>
    </>
  );
  return (
    <li data-event={event.title} data-kind={event.kind} className="relative">
      {event.link ? (
        <button
          type="button"
          className="flex w-full items-start gap-[12px] px-[18px] py-[9px] text-left"
          onClick={() => onOpenLink?.(event.link!)}
        >
          {body}
        </button>
      ) : (
        <div className="flex items-start gap-[12px] px-[18px] py-[9px]">{body}</div>
      )}
    </li>
  );
}

function CheckpointRow({
  checkpoint,
  onOpen,
  onStar,
}: {
  checkpoint: Checkpoint;
  onOpen?: ((key: string) => void) | undefined;
  onStar?: ((key: string) => void) | undefined;
}): JSX.Element {
  return (
    <li
      data-checkpoint={checkpoint.key}
      data-state={checkpoint.state}
      className="flex h-[56px] items-center gap-[8px] border-b border-hairline px-[12px]"
    >
      <button
        type="button"
        aria-label={`${COPY.star} ${checkpoint.name}`}
        aria-pressed={Boolean(checkpoint.starred)}
        className="text-[13px] text-ink-3"
        onClick={() => onStar?.(checkpoint.key)}
      >
        {checkpoint.starred ? "★" : "☆"}
      </button>
      <button
        type="button"
        className="flex min-w-0 flex-1 flex-col text-left"
        onClick={() => onOpen?.(checkpoint.key)}
      >
        <span className="text-[13px] font-medium">{checkpoint.name}</span>
        <span className="text-[11.5px] text-ink-3">
          {checkpoint.author} · {checkpoint.at}
        </span>
      </button>
      {checkpoint.state === "current" ? (
        <Pill variant="neutral">{COPY.current}</Pill>
      ) : checkpoint.state === "proposed" ? (
        <span className="flex items-center gap-[6px]">
          <Pill variant="amber" size="state">
            {COPY.proposed}
          </Pill>
          <Button variant="link" size="sm" onClick={() => onOpen?.(checkpoint.key)}>
            {COPY.review}
          </Button>
        </span>
      ) : (
        <Pill variant="green-tint">{COPY.approved}</Pill>
      )}
    </li>
  );
}

export function Activity({
  frame,
  onOpenCheckpoint,
  onCompare,
  onStar,
  onOpenLink,
}: ActivityProps): JSX.Element {
  const initial: Kind | "all" = frame === "e" ? "agent" : frame === "e2" ? "issue" : "all";
  const [filter, setFilter] = useState<Kind | "all">(initial);
  const [query, setQuery] = useState("");
  const proposed = frame === "b" || frame === "b2";
  const fixed = frame === "c";
  const events = useMemo(() => {
    let all: Event[] = [...EVENTS];
    if (proposed) all = [PROPOSED_EVENT, ...all];
    if (frame === "d") all = [...DELIVERED, ...all];
    if (frame === "e2") all = all.filter((e) => e.kind !== "issue"); // a filter with no rows
    const byKind = filter === "all" ? all : all.filter((e) => e.kind === filter);
    const q = query.trim().toLowerCase();
    return q
      ? byKind.filter((e) => `${e.title} ${e.sub ?? ""}`.toLowerCase().includes(q))
      : byKind;
  }, [filter, query, proposed, frame]);
  const checkpoints = proposed ? [PROPOSED_CHECKPOINT, ...CHECKPOINTS] : CHECKPOINTS;
  const chip = proposed ? COPY.chipProposed : fixed ? COPY.chipNone : COPY.chip;
  return (
    <div data-screen="TAX-07" data-frame={frame} className="flex flex-col">
      <header className="flex h-[42px] items-center justify-between px-[12px]">
        <span className="flex items-center gap-[8px]">
          <span data-chip className="flex items-center gap-[4px] text-[13px]">
            {proposed ? <span aria-hidden className="size-[6px] rounded-full bg-amber" /> : null}
            {chip} ⌄
          </span>
          <span className="rounded-[8px] bg-card px-[8px] py-[2px] text-[12.5px] shadow-e1">
            {COPY.sync} ⌄
          </span>
        </span>
        <span className="flex items-center gap-[8px]">
          <span className="text-[15px] font-medium">{COPY.title}</span>
          <span className="text-ink-2">{COPY.client}</span>
          <Pill variant="amber" size="state">
            {COPY.state}
          </Pill>
        </span>
        <span className="text-[13px] text-ink-2">Assistant</span>
      </header>
      <nav aria-label="Return" className="flex h-[44px] items-center justify-center gap-[6px]">
        {(fixed ? COPY.tabsAfterFix : COPY.tabs).map((t) => (
          <span
            key={t}
            data-tab={t}
            aria-current={t === "Activity" ? "page" : undefined}
            className={`rounded-[8px] px-[10px] py-[4px] text-[13px] ${t === "Activity" ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
          >
            {t}
          </span>
        ))}
      </nav>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label={COPY.activity}
          className="flex w-[1006px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[46px] items-center justify-between px-[12px]">
            <input
              aria-label={COPY.search}
              placeholder={COPY.search}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
              }}
              className="h-[28px] w-[260px] rounded-[6px] bg-nested px-[8px] text-[13px]"
            />
            <span className="text-[14.5px] font-medium">{COPY.activity}</span>
            <select
              aria-label="Filter events"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value as Kind | "all");
              }}
              className="h-[28px] rounded-[6px] bg-nested px-[6px] text-[13px]"
            >
              {FILTERS.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          {events.length === 0 ? (
            <p className="px-[18px] py-[24px] text-[13px] text-ink-2">{COPY.emptyFilter}</p>
          ) : (
            <ol className="relative flex flex-col">
              <span aria-hidden className="absolute bottom-0 left-[107px] top-0 w-px bg-hair" />
              {events.map((e) => (
                <Row key={`${e.date} ${e.time} ${e.title}`} event={e} onOpenLink={onOpenLink} />
              ))}
            </ol>
          )}
        </section>
        <section
          aria-label={COPY.checkpoints}
          className="flex w-[360px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[46px] items-center justify-center gap-[8px] px-[12px]">
            <span className="text-[14.5px] font-medium">{COPY.checkpoints}</span>
            <Button variant="secondary" size="sm" onClick={onCompare}>
              {COPY.compare}
            </Button>
          </div>
          <ul>
            {checkpoints.map((c) => (
              <CheckpointRow
                key={c.key}
                checkpoint={c}
                onOpen={onOpenCheckpoint}
                onStar={onStar}
              />
            ))}
          </ul>
          {frame === "b2" ? (
            <aside
              aria-label={COPY.drawer}
              data-drawer="SHL-16"
              className="border-t border-hairline p-[12px]"
            >
              <h3 className="text-[13.5px] font-medium">{PROPOSED_CHECKPOINT.name}</h3>
              <ul className="flex flex-col gap-[6px]">
                {PROPOSED_DIFF.map((d) => (
                  <li key={d.field} data-diff={d.field} className="flex flex-col text-[12.5px]">
                    <span>
                      {d.field} · {d.old} → {d.next}
                    </span>
                    <span className="text-ink-3">{d.cause}</span>
                  </li>
                ))}
              </ul>
              <span className="mt-[8px] flex gap-[6px]">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => onOpenCheckpoint?.(PROPOSED_CHECKPOINT.key)}
                >
                  {COPY.approve}
                </Button>
                <Button variant="secondary" size="sm">
                  {COPY.restore}
                </Button>
              </span>
            </aside>
          ) : null}
        </section>
      </div>
    </div>
  );
}
