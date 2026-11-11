// AUD-29 · Engagement activity log in the T2 cockpit canvas (P-05-T14; handoff AUD-29), fixture
// mode: the Timeline (76px right-aligned date column, marks on a hairline, day separators), the
// segmented counts the server gives (All · Human · via Agent · Policy), Type and Date chips, the
// live search (the text goes to the host's request body, never the URL), row Open routing by kind
// to a built screen or a registered planned link, Download only with `export.create` (the host
// steps up MFA), and the Policy empty state. Events are immutable: no edit or delete anywhere.
import { Button, EmptyState } from "@abacus/ui";
import { type JSX, useMemo, useState } from "react";
import {
  type ActivityEvent,
  COPY,
  COUNTS,
  EVENTS,
  type Frame,
  type Segment,
  type Target,
  separatorOf,
} from "./copy";

export interface ActivityLogProps {
  frame: Frame;
  /** The server's `allowed_actions` for the engagement's activity (`export.create` shows Download). */
  allowedActions?: readonly string[];
  /** A row's Open: the target screen (or its registered planned link). */
  onOpen?: (target: Target, event: ActivityEvent) => void;
  /** Download: the host steps up MFA and posts the export with the filters. */
  onDownload?: (segment: Segment, q: string) => void;
  /** The search text, for the host's POST …/audit-events/query body. */
  onSearch?: (q: string) => void;
}

const INITIAL: Record<Frame, { segment: Segment; q: string }> = {
  a: { segment: "all", q: "" },
  b: { segment: "agent", q: "" },
  c: { segment: "human", q: "" },
  d: { segment: "policy", q: "" },
  e: { segment: "all", q: "Materiality" },
  f: { segment: "all", q: "" },
};

function Mark({ mark }: { mark: ActivityEvent["mark"] }): JSX.Element {
  return (
    <span
      aria-hidden
      data-mark={mark}
      className={`z-10 flex size-[20px] shrink-0 items-center justify-center rounded-full text-[11px] ${mark === "check" ? "bg-espresso text-on-dark" : "bg-card text-ink-2"}`}
    >
      {mark === "check" ? "✓" : mark === "atom" ? "⚛" : "▸"}
    </span>
  );
}

export function ActivityLog({
  frame,
  allowedActions = [],
  onOpen,
  onDownload,
  onSearch,
}: ActivityLogProps): JSX.Element {
  const [segment, setSegment] = useState<Segment>(INITIAL[frame].segment);
  const [q, setQ] = useState(INITIAL[frame].q);
  const rows = useMemo(() => {
    const bySegment =
      segment === "policy"
        ? []
        : EVENTS.filter((e) => segment === "all" || (segment === "agent") === e.agent);
    const needle = q.trim().toLowerCase();
    return needle
      ? bySegment.filter((e) => `${e.title} ${e.detail}`.toLowerCase().includes(needle))
      : bySegment;
  }, [segment, q]);
  const canDownload = allowedActions.includes("export.create");
  let lastSeparator = "";
  return (
    <section
      data-screen="AUD-29"
      data-frame={frame}
      aria-label={COPY.title}
      className="flex flex-col rounded-pane bg-card shadow-e1"
    >
      <div className="flex h-[46px] items-center justify-between px-[14px]">
        <input
          aria-label={COPY.search}
          placeholder={COPY.search}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            onSearch?.(e.target.value);
          }}
          className="h-[28px] w-[200px] rounded-[6px] bg-nested px-[8px] text-[13px]"
        />
        <span className="text-[14.5px] font-medium">{COPY.title}</span>
        <span className="flex items-center gap-[8px]">
          <span className="text-[12.5px] text-ink-3">{COPY.events(COUNTS.all)}</span>
          {canDownload ? (
            <Button
              variant="ghost"
              size="sm"
              aria-label={COPY.download}
              onClick={() => onDownload?.(segment, q)}
            >
              ⤓
            </Button>
          ) : null}
        </span>
      </div>
      <div className="flex h-[44px] items-center gap-[8px] px-[14px]">
        <div role="tablist" aria-label="Actor" className="flex rounded-[8px] bg-nested p-[2px]">
          {(Object.keys(COPY.segments) as Segment[]).map((s) => (
            <button
              key={s}
              type="button"
              role="tab"
              aria-selected={segment === s}
              data-segment={s}
              onClick={() => {
                setSegment(s);
              }}
              className={`rounded-[6px] px-[8px] text-[12.5px] ${segment === s ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
            >
              {`${COPY.segments[s]} ${String(COUNTS[s])}`}
            </button>
          ))}
        </div>
        <span className="rounded-[6px] bg-nested px-[8px] text-[12.5px]">{`${COPY.type} │ ${COPY.typeAll} ⇕`}</span>
        <span className="rounded-[6px] bg-nested px-[8px] text-[12.5px]">{`${COPY.date} │ ${COPY.since} ⇕`}</span>
      </div>
      {segment === "policy" ? (
        <EmptyState title={COPY.policyEmptyTitle}>{COPY.policyEmptyBody}</EmptyState>
      ) : rows.length === 0 ? (
        <p className="px-[18px] py-[24px] text-[13px] text-ink-2">{COPY.noMatch}</p>
      ) : (
        <ol className="relative flex flex-col">
          <span aria-hidden className="absolute bottom-0 left-[107px] top-0 w-px bg-hair" />
          {rows.map((e) => {
            const separator = separatorOf(e.date);
            const head = separator !== lastSeparator;
            lastSeparator = separator;
            return (
              <li
                key={`${e.date} ${e.time} ${e.title}`}
                data-event={e.title}
                data-agent={e.agent ? "true" : "false"}
              >
                {head ? (
                  <div
                    data-separator
                    className="h-[28px] px-[18px] pt-[8px] text-[11.5px] font-medium uppercase tracking-[.06em] text-ink-3"
                  >
                    {separator}
                  </div>
                ) : null}
                <div className="group flex items-start gap-[14px] px-[18px] py-[9px]">
                  <span className="flex w-[76px] shrink-0 flex-col items-end">
                    <span className="text-[12.5px] text-ink-2">{e.date}</span>
                    <span className="text-[11.5px] text-ink-3">{e.time}</span>
                  </span>
                  <Mark mark={e.mark} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-[13.5px] font-medium">{e.title}</span>
                    <span className="text-[12.5px] text-ink-2">{e.detail}</span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    data-open={e.target}
                    className={
                      frame === "f"
                        ? ""
                        : "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                    }
                    onClick={() => onOpen?.(e.target, e)}
                  >
                    {COPY.open}
                  </Button>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
