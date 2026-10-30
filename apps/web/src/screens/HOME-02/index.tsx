import type { HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import { humanGateCountsOptions, humanGateListOptions } from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  ErrorState,
  type IssueGroup,
  type IssueItem,
  IssueQueue,
  Skeleton,
  type ToolbarProps,
  QueueDetailLayout,
  date as formatDate,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type KeyboardEvent, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenHref } from "../../app-core/open";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  type Band,
  HOME_MESSAGES,
  HOME_POLL_MS,
  HOME_SEGMENTS,
  HOME_STALE_MS,
  HomeSegmented,
  dueChip,
  visibleBands,
} from "../../domain/home";
import { COPY } from "./copy";
import { MY_WORK, openHref } from "./hosts";

// HOME-02 · My approvals & review queue, the queue (I-01-T16; docs/screens/HOME-02.md) on T9
// QueueDetailLayout preset close-review: the subbar ("Approvals" + the viewer, the Home segmented
// with Approvals active, Sort │ Deadline, Select), the 310 queue under "Waiting on you" with Show
// done, 49 px bands in the fixed band order with the counts endpoint's numbers, 50–72 px rows with
// the class glyph and "<due> · <words>" sub-lines (risk in words, never colour alone), the selected
// row in sel-bg, J/K and Enter, `?gate=` and the empty state (f). The detail (I-01-T17), evidence
// (T18) and bulk Select (T19) fill the other panes later; here the detail names the selected gate
// and its "Open" goes to the gate's own host (`hosts.ts`: its `subject_route` through the manifest's
// builders, a return's final approval on TAX-02), and the segmented's "My work" to HOME-01. A row
// is a link to where the gate is decided, never a decision control (INV-1). Behind `home.approvals`
// (created here).

const POLL = {
  refetchInterval: HOME_POLL_MS,
  staleTime: HOME_STALE_MS,
  refetchOnWindowFocus: true,
};

const GLYPH_OF: Readonly<Record<HumanGateOut["kind"], NonNullable<IssueItem["glyph"]>>> = {
  decision: { icon: "circle-help", label: COPY.glyph.decision },
  sign_off_request: { icon: "circle-check", label: COPY.glyph.sign_off },
  proposal: { icon: "sparkles", label: COPY.glyph.other },
  send: { icon: "send", label: COPY.glyph.other },
  final_approval: { icon: "circle-check", label: COPY.glyph.other },
  export: { icon: "circle-check", label: COPY.glyph.other },
  release: { icon: "circle-check", label: COPY.glyph.other },
  evidence_review: { icon: "file-search", label: COPY.glyph.other },
};

function itemOf(gate: HumanGateOut, today: string, now: Date): IssueItem {
  const due =
    gate.due_on === null ? null : dueChip(today, gate.due_on, (iso) => formatDate(iso, { now }));
  const words = gate.blocked ? HOME_MESSAGES.blocked : (gate.context ?? null);
  return {
    id: gate.id,
    title: gate.title ?? gate.subkind,
    sub: [due?.label, words].filter((p) => p != null && p !== "").join(" · "),
    ...(gate.blocked || due?.risk === "overdue" ? { subTone: "amber" as const } : {}),
    glyph: gate.blocked
      ? { icon: "triangle-alert", label: COPY.glyph.blocked, tone: "amber" }
      : GLYPH_OF[gate.kind],
  };
}

function groupsOf(
  counts: HumanGateCountsOut,
  gates: readonly HumanGateOut[],
  today: string,
  now: Date,
): IssueGroup[] {
  return visibleBands(counts.bands).map((band: Band) => ({
    id: band,
    label: HOME_MESSAGES.bands[band],
    // The server's count, never counted here (the badge rule, DF-25).
    count: String(counts.bands[band]),
    items: gates.filter((g) => g.band === band).map((g) => itemOf(g, today, now)),
  }));
}

export interface HOME02Props {
  /** `?gate=`: the selected gate (an opaque id); the first row when absent. */
  gate?: string | null;
  onGate?: (gate: string | null) => void;
  /** Enter on a row, and "Open": the gate's host as an href (default: its `subject_route`). */
  hrefOf?: (gate: HumanGateOut) => string | undefined;
  /** The gallery's frame: the firm toolbar drawn inside the window. */
  toolbar?: ToolbarProps;
  height?: number;
  initialDone?: boolean;
}

export function HOME02({
  gate: gateParam = null,
  onGate,
  hrefOf = openHref,
  toolbar,
  height,
  initialDone = false,
}: HOME02Props): JSX.Element {
  const now = useNow();
  const session = useSession();
  const today = now.toISOString().slice(0, 10);
  const [done, setDone] = useState(initialDone);
  const [chosen, setChosen] = useState<string | null>(gateParam);
  const [said, setSaid] = useState("");
  const queueRef = useRef<HTMLDivElement>(null);
  const counts = useQuery({ ...humanGateCountsOptions(), ...POLL });
  const list = useQuery({
    ...humanGateListOptions({
      query: { assignee: "me", state: done ? "done" : "open", sort: "deadline", limit: 200 },
    }),
    ...POLL,
  });
  const gates = list.data?.items ?? [];
  const groups: IssueGroup[] =
    counts.data === undefined
      ? []
      : done
        ? [
            {
              id: "done",
              label: COPY.done,
              count: String(list.data?.total ?? 0),
              items: gates.map((g) => itemOf(g, today, now)),
            },
          ]
        : groupsOf(counts.data, gates, today, now);
  const order = groups.flatMap((g) => g.items);
  const selectedId = order.some((i) => i.id === chosen) ? chosen : (order[0]?.id ?? null);
  const selected = gates.find((g) => g.id === selectedId);
  const href = selected === undefined ? undefined : hrefOf(selected);
  const open = useOpenHref();

  const select = (id: string | null, focus = false): void => {
    setChosen(id);
    onGate?.(id);
    const item = order.find((i) => i.id === id);
    if (item !== undefined) setSaid(COPY.selected(item.title));
    if (focus && id !== null) {
      queueRef.current?.querySelector<HTMLButtonElement>(`[data-issue-row="${id}"]`)?.focus();
    }
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const at = order.findIndex((i) => i.id === selectedId);
    if (event.key === "j" || event.key === "k") {
      const next =
        order[event.key === "j" ? Math.min(at + 1, order.length - 1) : Math.max(at - 1, 0)];
      if (next === undefined) return;
      event.preventDefault();
      select(next.id, true);
    } else if (event.key === "Enter" && href !== undefined) {
      event.preventDefault();
      open(href);
    }
  };

  const total = counts.data?.total;
  const record = (
    <div
      data-home02="subbar"
      className="relative flex h-(--subbar-h) flex-none items-center gap-[8px] px-(--edge-app)"
    >
      <span className="flex items-baseline gap-[6px]">
        <span className="text-record font-medium">{COPY.title}</span>
        <span className="text-record text-ink-2">{session.user?.displayName ?? ""}</span>
      </span>
      <span className="absolute left-1/2 -translate-x-1/2">
        <HomeSegmented
          total={total}
          segments={undefined}
          active={HOME_SEGMENTS.approvals}
          onChange={(label) => {
            if (label === HOME_SEGMENTS.myWork) open(MY_WORK);
          }}
        />
      </span>
      <span className="ml-auto flex items-center gap-[8px]">
        <span className="inline-flex h-[29px] items-center gap-[6px] rounded-pill bg-card px-[11px] text-body shadow-e1">
          <span className="text-ink-2">{COPY.sort}</span>
          <span aria-hidden="true" className="h-[14px] w-px bg-rule" />
          {COPY.deadline}
        </span>
        {PLANNED_VISIBLE && (
          <Button variant="secondary" size="sm" disabled>
            {COPY.select}
          </Button>
        )}
      </span>
    </div>
  );

  const queueBody =
    counts.isError || list.isError ? (
      <ErrorState
        noun={COPY.error}
        onRetry={() => {
          void counts.refetch();
          void list.refetch();
        }}
      />
    ) : counts.data === undefined || list.data === undefined ? (
      <div aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-[44px] w-full" />
        ))}
      </div>
    ) : order.length === 0 ? (
      <EmptyState
        icon="inbox"
        title={COPY.empty}
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setDone(true);
            }}
          >
            {COPY.showDone}
          </Button>
        }
      />
    ) : (
      // J/K move the selection and focus the row (its aria-current is announced, and the live
      // line says which); Enter opens the gate's host.
      <div ref={queueRef} onKeyDown={onKey} data-home02="queue">
        <IssueQueue
          variant="severity"
          label={COPY.queue}
          groups={groups}
          selected={selectedId}
          onSelect={(item) => {
            select(item.id);
          }}
        />
        <p aria-live="polite" className="sr-only">
          {said}
        </p>
      </div>
    );

  const detailBody =
    selected === undefined ? null : (
      <div className="flex flex-col">
        <h3 className="bg-shell px-[14px] py-[12px] text-record leading-[1.3] font-medium">
          {selected.title ?? selected.subkind}
        </h3>
        {selected.context != null && (
          <p className="px-[14px] py-[10px] text-dense leading-[1.55] text-ink-2">
            {selected.context}
          </p>
        )}
      </div>
    );

  return (
    <div data-screen="HOME-02" className="flex min-h-0 flex-1 flex-col">
      <QueueDetailLayout
        preset="close-review"
        {...(toolbar === undefined
          ? { bare: true, toolbar: { nav: [], active: "Home", firm: "" } }
          : { toolbar: { ...toolbar, active: "Home" }, embedded: true })}
        {...(height === undefined ? {} : { height })}
        record={record}
        queue={{
          title: COPY.waiting,
          right: (
            <button
              type="button"
              aria-pressed={done}
              onClick={() => {
                setDone((d) => !d);
                setChosen(null);
              }}
              className="text-body text-ink-3 hover:text-ink"
            >
              {done ? COPY.hideDone : COPY.showDone}
            </button>
          ),
          body: queueBody,
        }}
        detail={{
          title: COPY.detail,
          body: detailBody,
          ...(href === undefined
            ? {}
            : {
                footer: (
                  <Button variant="secondary" size="sm" asChild>
                    <a href={href}>{COPY.open}</a>
                  </Button>
                ),
              }),
        }}
        evidence={[
          <section
            key="evidence"
            aria-label={COPY.evidence}
            className="pane flex min-h-0 flex-1 flex-col"
          >
            <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
              <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.evidence}</h2>
            </div>
          </section>,
        ]}
      />
    </div>
  );
}
