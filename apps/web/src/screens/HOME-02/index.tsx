import type { HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import {
  Button,
  EmptyState,
  ErrorState,
  type IssueGroup,
  type IssueItem,
  Icon,
  IssueQueue,
  Skeleton,
  type ToolbarProps,
  QueueDetailLayout,
  date as formatDate,
} from "@abacus/ui";
import { useQueryClient } from "@tanstack/react-query";
import { type JSX, type KeyboardEvent, useRef, useState } from "react";
import { BulkSignOffSheet } from "../SHL-12/Bulk";
import { useNow } from "../../app-core/clock";
import { useOpenHref, useOpenOverlay } from "../../app-core/open";
import type { OverlayRef } from "../../app-core/overlays";
import { useSession } from "../../app-core/session";
import {
  type Band,
  type EvidenceSummaryOf,
  HOME_MESSAGES,
  HOME_SEGMENTS,
  HomeSegmented,
  dueChip,
  invalidateGates,
  useApprovalsList,
  useDoneGates,
  useGateCounts,
  useHome,
  visibleBands,
} from "../../domain/home";
import { COPY } from "./copy";
import { type DecisionDraft, GateDetailBody, GateDetailFooter } from "./Detail";
import { EvidencePane } from "./Evidence";
import { MY_WORK, openHref, openOverlayOf } from "./hosts";

// HOME-02 · My approvals & review queue, the queue (I-01-T16; docs/screens/HOME-02.md) on T9
// QueueDetailLayout preset close-review: the subbar ("Approvals" + the viewer, the Home segmented
// with Approvals active, Sort │ Deadline, Select), the 310 queue under "Waiting on you" with Show
// done, 49 px bands in the fixed band order with the counts endpoint's numbers, 50–72 px rows with
// the class glyph and "<due> · <words>" sub-lines (risk in words, never colour alone), the selected
// row in sel-bg, J/K and Enter, `?gate=` and the empty state (f). The detail pane renders the
// selected gate by class (I-01-T17, `Detail.tsx`): the inline decision card, a sign-off blocked or
// ready, an agent output, approvals and sends, and the generic fallback; every verb there is the
// person's HumanAction, opening its overlay. A gate decided here stays in the detail (b) after it
// leaves the queue, and `?gate=` on a done gate finds it among the done rows. The evidence pane
// (I-01-T18, `Evidence.tsx`) shows the owner's summary and the cited sources through SHL-08's
// viewer. Select (I-01-T19) puts a checkbox on every sign-off row: enabled on the server's
// `bulk_eligible` rows, disabled with "Blocked" on blocked ones, none on other classes; the 52 px
// bar ("4 selected · Sign off 4 as Partner") opens SHL-12 f over the chosen targets, which signs
// and shows each item's result. Enter and the generic "Open" go to the gate's own host
// (`hosts.ts`), and the segmented's "My work" to HOME-01. A row is a link to where the gate is
// decided, never a decision control (INV-1). Behind `home.approvals` (created here).

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

/** Select mode's checkbox on a sign-off row (AC8.1): the server says which rows may be signed. */
interface Picking {
  on: boolean;
  chosen: ReadonlySet<string>;
  toggle: (id: string, checked: boolean) => void;
}

function checkOf(gate: HumanGateOut, picking: Picking | undefined): IssueItem["check"] {
  if (picking?.on !== true || gate.kind !== "sign_off_request") return undefined;
  const title = gate.title ?? gate.subkind;
  const blocked = gate.blocked || !gate.bulk_eligible;
  return {
    label: COPY.bulk.check(title),
    checked: !blocked && picking.chosen.has(gate.id),
    ...(blocked ? { disabled: true, reason: "blocked" } : {}),
    onChange: (checked) => {
      picking.toggle(gate.id, checked);
    },
  };
}

/** A row's due words (`row.subline`): a decision counts the days and a day-away one reads in the
 * red ink; every other class shows the date, and "Overdue" once past it. */
function dueWords(
  gate: HumanGateOut,
  today: string,
  now: Date,
): { lead?: string; plain?: string; overdue: boolean } {
  if (gate.due_on === null) return { overdue: false };
  const on = formatDate(gate.due_on, { now });
  const chip = dueChip(today, gate.due_on, (iso) => formatDate(iso, { now }));
  if (chip.risk === "overdue") return { plain: chip.label, overdue: true };
  if (gate.kind !== "decision") return { plain: on, overdue: false };
  const days = Math.round((Date.parse(gate.due_on) - Date.parse(today)) / 86_400_000);
  const counted = HOME_MESSAGES.due.inDays(on, days);
  return chip.risk === "due_soon" && days <= 1
    ? { lead: counted, overdue: false }
    : { plain: counted, overdue: false };
}

function itemOf(gate: HumanGateOut, today: string, now: Date, picking?: Picking): IssueItem {
  const check = checkOf(gate, picking);
  const due = dueWords(gate, today, now);
  // The owner's words name the block where they can ("Blocked · off 6,200"); the word itself
  // otherwise, so a blocked row is never colour alone.
  const words =
    gate.blocked && gate.context?.startsWith(HOME_MESSAGES.blocked) !== true
      ? HOME_MESSAGES.blocked
      : (gate.context ?? null);
  const rest = [due.plain, words].filter((p) => p != null && p !== "").join(" · ");
  return {
    id: gate.id,
    title: gate.title ?? gate.subkind,
    sub: rest,
    ...(due.lead === undefined ? {} : { subLead: due.lead }),
    ...(gate.blocked || due.overdue ? { subTone: "amber" as const } : {}),
    glyph: gate.blocked
      ? { icon: "triangle-alert", label: COPY.glyph.blocked, tone: "amber" }
      : GLYPH_OF[gate.kind],
    ...(check === undefined ? {} : { check }),
  };
}

function groupsOf(
  counts: HumanGateCountsOut,
  gates: readonly HumanGateOut[],
  today: string,
  now: Date,
  picking: Picking,
): IssueGroup[] {
  return visibleBands(counts.bands).map((band: Band) => ({
    id: band,
    label: HOME_MESSAGES.bands[band],
    // The server's count, never counted here (the badge rule, DF-25).
    count: String(counts.bands[band]),
    items: gates.filter((g) => g.band === band).map((g) => itemOf(g, today, now, picking)),
  }));
}

export interface HOME02Props {
  /** `?gate=`: the selected gate (an opaque id); the first row when absent. */
  gate?: string | null;
  onGate?: (gate: string | null) => void;
  /** Enter on a row, and "Open": the gate's host as an href (default: its `subject_route`). */
  hrefOf?: (gate: HumanGateOut) => string | undefined;
  /** Enter on a row, and "Open", for a decision or sign-off row: its sheet as a `?ov=` layer over
   * the queue (P-04-T52), ahead of `hrefOf`. */
  overlayOf?: (gate: HumanGateOut) => OverlayRef | undefined;
  /** The gallery's frame: the firm toolbar drawn inside the window. */
  toolbar?: ToolbarProps;
  height?: number;
  initialDone?: boolean;
  /** Artboard e: Select mode with every eligible row checked. */
  initialSelecting?: boolean;
  /** The owners' evidence summaries (I-01-T18): fixtures today, tax fixture-only until T-05. */
  summaryOf?: EvidenceSummaryOf;
}

export function HOME02({
  gate: gateParam = null,
  onGate,
  hrefOf = openHref,
  overlayOf = openOverlayOf,
  toolbar,
  height,
  initialDone = false,
  initialSelecting = false,
  summaryOf,
}: HOME02Props): JSX.Element {
  const now = useNow();
  const session = useSession();
  const today = now.toISOString().slice(0, 10);
  const [done, setDone] = useState(initialDone);
  const [chosen, setChosen] = useState<string | null>(gateParam);
  const [said, setSaid] = useState("");
  const [drafts, setDrafts] = useState<Readonly<Record<string, DecisionDraft>>>({});
  const held = useRef<HumanGateOut | null>(null);
  const [selecting, setSelecting] = useState(initialSelecting);
  // null: every eligible row, until the first toggle (artboard e).
  const [pickedOverride, setPicked] = useState<ReadonlySet<string> | null>(
    initialSelecting ? null : new Set(),
  );
  const [bulkOpen, setBulkOpen] = useState(false);
  const queueRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const counts = useGateCounts(null);
  const view = useHome(null).data;
  const list = useApprovalsList(done ? "done" : "open");
  const gates = list.data?.items ?? [];
  const eligible = gates.filter(
    (g) => g.kind === "sign_off_request" && g.bulk_eligible && !g.blocked,
  );
  const picked = pickedOverride ?? new Set(eligible.map((g) => g.id));
  const picking: Picking = {
    on: selecting,
    chosen: picked,
    toggle: (id, checked) => {
      const next = new Set(picked);
      if (checked) next.add(id);
      else next.delete(id);
      setPicked(next);
    },
  };
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
        : groupsOf(counts.data, gates, today, now, picking);
  const order = groups.flatMap((g) => g.items);
  const listed = order.some((i) => i.id === chosen);
  // `?gate=` naming a done gate (b): look among the done rows once the open list has loaded.
  const doneRows = useDoneGates(
    !done && chosen !== null && list.data !== undefined && !listed && held.current?.id !== chosen,
  );
  const fromDone = doneRows.data?.items.find((g) => g.id === chosen);
  if (fromDone !== undefined && held.current?.id !== fromDone.id) held.current = fromDone;
  const keep = !listed && chosen !== null && held.current?.id === chosen;
  const selectedId = listed || keep ? chosen : (order[0]?.id ?? null);
  const selected =
    gates.find((g) => g.id === selectedId) ?? (keep ? held.current : null) ?? undefined;
  // A gate decided here leaves the queue on the next read; the detail keeps showing it (b).
  if (selected !== undefined && listed) held.current = selected;
  const layer = selected === undefined ? undefined : overlayOf(selected);
  const href = selected === undefined || layer !== undefined ? undefined : hrefOf(selected);
  const open = useOpenHref();
  const openOverlay = useOpenOverlay();

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
    } else if (event.key === "Enter" && layer !== undefined) {
      event.preventDefault();
      openOverlay(layer);
    } else if (event.key === "Enter" && href !== undefined) {
      event.preventDefault();
      open(href);
    }
  };

  const total = counts.data?.total;
  const anyEligible = gates.some((g) => g.kind === "sign_off_request" && g.bulk_eligible);
  // The picked rows still open and eligible (a row the server moved drops out of the count).
  const chosenGates = gates.filter((g) => picked.has(g.id) && g.bulk_eligible && !g.blocked);
  const level = chosenGates[0]?.role ?? undefined;
  const role = COPY.bulk.roles[level ?? ""] ?? "";
  const bar =
    selecting && chosenGates.length > 0 ? (
      <div
        data-home02="bulk-bar"
        className="sticky bottom-[8px] mx-[8px] flex h-[52px] items-center gap-[10px] rounded-nested bg-card px-[12px] shadow-e2"
      >
        <span className="flex-1 text-body">{COPY.bulk.selected(chosenGates.length)}</span>
        <Button
          variant="primary"
          size="lg"
          aria-haspopup="dialog"
          onClick={() => {
            setBulkOpen(true);
          }}
        >
          {COPY.bulk.signOff(chosenGates.length, role)}
        </Button>
      </div>
    ) : null;
  const record = (
    <div
      data-home02="subbar"
      className="relative flex h-(--subbar-h) flex-none items-center gap-[8px] px-(--edge-app)"
    >
      <span className="flex items-baseline gap-[8px]">
        <span className="text-title font-medium">{COPY.title}</span>
        <span className="text-title text-ink-2">{session.user?.displayName ?? ""}</span>
      </span>
      <span className="absolute left-1/2 -translate-x-1/2">
        <HomeSegmented
          total={total}
          segments={view?.segments}
          active={HOME_SEGMENTS.approvals}
          size="small"
          onChange={(label) => {
            if (label === HOME_SEGMENTS.myWork) open(MY_WORK);
          }}
        />
      </span>
      <span className="ml-auto flex items-center gap-[8px]">
        <span className="inline-flex h-[29px] items-center gap-[8px] rounded-pill bg-card px-[11px] text-body shadow-e1">
          <span className="flex items-center gap-[6px] text-ink-2">
            <Icon name="list-filter" size={13} />
            {COPY.sort}
          </span>
          <span aria-hidden="true" className="h-[14px] w-px bg-rule" />
          <span className="flex items-center gap-[6px]">
            {COPY.deadline}
            <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
          </span>
        </span>
        <Button
          variant="secondary"
          size="sm"
          aria-pressed={selecting}
          className={selecting ? "bg-sel-bg" : undefined}
          disabled={done || !anyEligible}
          onClick={() => {
            setSelecting((s) => !s);
            setPicked(new Set());
          }}
        >
          {COPY.select}
        </Button>
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
          stacked
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
        {bar}
      </div>
    );

  const detailProps =
    selected === undefined
      ? undefined
      : {
          gate: selected,
          href: hrefOf(selected),
          draft: drafts[selected.id] ?? { words: "" },
          onDraft: (draft: DecisionDraft) => {
            setDrafts((d) => ({ ...d, [selected.id]: draft }));
          },
        };

  return (
    <div data-screen="HOME-02" className="flex min-h-0 flex-1 flex-col">
      <QueueDetailLayout
        preset="close-review"
        {...(toolbar === undefined
          ? { bare: true, toolbar: { nav: [], active: "Home", firm: "" } }
          : { toolbar: { ...toolbar, active: "Home" }, embedded: true })}
        {...(height === undefined ? {} : { height })}
        record={record}
        recordHeight={42}
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
              className="mr-[10px] text-body text-ink-3 hover:text-ink"
            >
              {done ? COPY.hideDone : COPY.showDone}
            </button>
          ),
          body: queueBody,
        }}
        detail={{
          title: COPY.detail,
          body:
            detailProps === undefined ? null : (
              <GateDetailBody key={detailProps.gate.id} {...detailProps} />
            ),
          ...(detailProps === undefined
            ? {}
            : { footer: <GateDetailFooter key={detailProps.gate.id} {...detailProps} /> }),
        }}
        evidence={[
          <EvidencePane
            key="evidence"
            gate={selected}
            {...(summaryOf === undefined ? {} : { summaryOf })}
          />,
        ]}
      />
      {bulkOpen && (
        <BulkSignOffSheet
          open
          onOpenChange={(open) => {
            setBulkOpen(open);
            if (!open) {
              setSelecting(false);
              setPicked(new Set());
            }
          }}
          targets={chosenGates.map((g) => ({ type: g.subject.type, id: g.subject.id }))}
          {...(level === undefined ? {} : { level })}
          onSigned={() => {
            void invalidateGates(queryClient);
          }}
        />
      )}
    </div>
  );
}
