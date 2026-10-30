import type {
  AuditCockpitOut,
  SourceDocumentGroupOut,
  SourceDocumentRowOut,
  SourceDocumentsOut,
} from "@abacus/api-client";
import { reasonCodesOptions } from "@abacus/api-client/query";
import {
  Button,
  type CockpitCanvas,
  DEFAULT_TZ,
  Dialog,
  EmptyState,
  Icon,
  Menu,
  PaneAction,
  Pill,
  RadioGroup,
  SearchField,
  SourceDocGroup,
  StatusDisc,
  Tooltip,
  ViewStateBody,
  type ViewState,
  date,
  toast,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type KeyboardEvent, useEffect, useMemo, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { useOverlays } from "../../app-core/overlay-host";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { AgentDock } from "../../domain/agents";
import {
  AgentActivityTab,
  AuditCockpit,
  DockViewer,
  isNotFound,
  useAgentTab,
  useAuditCockpit,
  useSourceDocumentDecisions,
  useSourceDocuments,
} from "../../domain/audits";
import {
  FollowUpSheet,
  type FollowUpSelection,
  LIVE_POLL_MS,
  ReturnDialog,
  type ReturnTarget,
  useClientContacts,
  useDelegate,
} from "../../domain/requests";
import { ScreeningCardHost, useFlagCitations, useScreeningCard } from "../../domain/screening";
import { COPY } from "./copy";

// AUD-03 · Source documents / PBC with viewer (A-01-T15, A-01-T16; docs/screens/AUD-03.md): the
// AUD-02 cockpit at Source Documents with the audit split (rail 330 · canvas 536 · viewer 490: the
// dock widened to the `--ev-w` token, its Viewer tab open). Every row names who owes it and when,
// or the file that answers it with the matcher's confidence, its "Linked (n)" count and the 12 px
// screening glyph. Selecting a row loads the viewer: an upload with the Accept / Return strip and
// the C-34 ScreeningCard above the masked page, or a requested row's "Not received yet". Each
// artboard is its data (fixtures/scenarios/AUD-03.ts):
//
//   a  E0, 9:41 AM: BrokerWindow selected; Gordon Whitfield's holdings, SSNs masked
//   b  the certified trust report: Match 94%, two passed checks; Accept → 12 of 24
//   c  Sep 9: the matcher's 62% proposal on Schedule of Account Balances held, flagged
//   d  c with "Return…" pressed: the ReturnDialog, Wrong document preselected
//   e  the IRS opinion letter (requested from Dana Kowalski): Remind, Request from third party…
//   f  late September: every request received, "Nothing missing"
//   g  Sep 21: the rows due Sep 18 still requested read "Overdue" (derived, never stored)
//
// Nothing here accepts, returns or sends by itself: Accept and Return are a person's clicks
// (`evidence.accept` / `evidence.reject`, human only), "Remind…" opens P-06's follow-up sheet
// where only Send sends, and the screening card never decides (INV-1, DEC-48).

export type Sort = "missing_first" | "received_first";

export interface AUD03Props {
  /** The assurance work item (`$auditId`). */
  auditId: string;
  /** The selected request (`?item=`). */
  item?: string | null;
  onItem?: (item: string | null) => void;
  /** `?sort=`; "Missing first" by default. */
  sort?: Sort;
  onSort?: (sort: Sort) => void;
  /** `?q=`: the search over request titles and file paths. */
  q?: string;
  onQuery?: (q: string) => void;
  /** d: the ReturnDialog opens on the selected upload as the artboard opens. */
  returning?: boolean;
  /** "All Audits" (AUD-01). */
  onBack?: () => void;
  /** A rail row other than Source Documents: AUD-02 at that section. */
  onSection?: (key: string) => void;
  /** "+ Add": the SHL-14 composer over the work item's PBC binder. */
  onAdd?: (binderId: string) => void;
  embedded?: boolean;
}

const SOURCE_DOCUMENTS = "source_documents";
/** The page in the 490 viewer: the pane less its 12 px well padding and the scrollbar. */
const VIEWER_PAGE = 456;

type Row = SourceDocumentRowOut;

const isOpen = (row: Row): boolean => row.status === "requested" || row.status === "returned";
const fileName = (path: string): string => path.slice(path.lastIndexOf("/") + 1);

// ---- The canvas ----------------------------------------------------------------------------------

function ScreeningGlyph({ verdict }: { verdict: NonNullable<Row["screening"]> }): JSX.Element {
  const label = COPY.row.screening[verdict];
  return (
    <Tooltip content={label}>
      <span data-screening-glyph={verdict} className="inline-flex flex-none align-middle">
        {verdict === "passed" ? (
          <StatusDisc state="done" size={13} />
        ) : verdict === "flagged" ? (
          <Icon name="triangle-alert" size={12} className="text-amber-ink" aria-label={label} />
        ) : (
          <StatusDisc state="todo" size={13} />
        )}
      </span>
    </Tooltip>
  );
}

function StatusMark({ row, reason }: { row: Row; reason: string | null }): JSX.Element {
  if (row.status === "received") {
    return (
      <span data-row-status="received" className="flex flex-none items-center gap-[6px]">
        <span className="text-dense text-ink-2">{COPY.row.received}</span>
        <StatusDisc state="done" />
      </span>
    );
  }
  if (row.status === "uploaded") {
    return (
      <Pill data-row-status="uploaded" variant="amber" size="sm" className="flex-none">
        {COPY.row.needsReview}
      </Pill>
    );
  }
  if (row.status === "returned") {
    return (
      <Pill data-row-status="returned" variant="red-tint" size="sm" className="flex-none">
        {COPY.row.returned(reason ?? "")}
      </Pill>
    );
  }
  if (row.overdue) {
    return (
      <Pill data-row-status="overdue" variant="red-tint" size="sm" className="flex-none">
        {COPY.row.overdue}
      </Pill>
    );
  }
  return (
    <span data-row-status="requested" className="flex flex-none items-center">
      <StatusDisc state="todo" />
    </span>
  );
}

function SubLine({ row, now, tz }: { row: Row; now: Date; tz: string }): JSX.Element {
  const upload = row.latest_upload ?? null;
  const day = (iso: string): string => date(iso, { now, tz });
  let text: string;
  if (upload === null) {
    text = COPY.row.requested(
      row.requested_at == null ? "" : day(row.requested_at),
      row.due_on == null ? null : day(row.due_on),
      row.owed_by?.display ?? null,
    );
  } else if (
    row.status === "uploaded" &&
    (upload.uploader_kind === "firm" || upload.uploader_kind === "connection") &&
    row.match_confidence != null
  ) {
    // The matcher proposed a file the firm already holds; a person decides (c; DEC-421).
    text = COPY.row.proposal(row.title, upload.path_label, row.match_confidence);
  } else {
    const parts = [upload.path_label];
    if (upload.uploader_kind === "client" || upload.uploader_kind === "third_party") {
      parts.push(COPY.row.uploaded(day(upload.uploaded_on)));
    }
    if (row.match_confidence != null) parts.push(COPY.row.matched(row.match_confidence));
    text = parts.join(" · ");
  }
  return (
    <span data-row-sub="" className="text-meta text-ink-3">
      {text}
      {upload !== null && row.screening != null && (
        <>
          {" "}
          <ScreeningGlyph verdict={row.screening} />
        </>
      )}
    </span>
  );
}

function SourceRow({
  row,
  selected,
  reason,
  now,
  tz,
  onOpen,
}: {
  row: Row;
  selected: boolean;
  reason: string | null;
  now: Date;
  tz: string;
  onOpen: (row: Row) => void;
}): JSX.Element {
  const linked = row.latest_upload == null ? null : (row.linked_count ?? null);
  return (
    <li
      data-aud03-row={row.request_item_id}
      data-status={row.status}
      className={
        selected
          ? "flex items-center bg-sel-bg hairline-b"
          : "flex items-center hairline-b hover:bg-nav-fill"
      }
    >
      <button
        type="button"
        data-aud03-open=""
        {...(selected ? { "aria-current": "true" as const } : {})}
        onClick={() => {
          onOpen(row);
        }}
        className="flex min-h-[52px] min-w-0 flex-1 items-center gap-[10px] py-[8px] pl-[12px] text-left focus-visible:outline-offset-[-2px]"
      >
        <Icon name="file" size={15} className="flex-none text-ink-3" />
        <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span className={selected ? "truncate text-body font-medium" : "truncate text-body"}>
            {row.title}
          </span>
          <SubLine row={row} now={now} tz={tz} />
        </span>
        <span
          data-linked=""
          aria-label={linked === null ? undefined : COPY.row.linked(linked)}
          className="flex w-[56px] flex-none items-center justify-end gap-[4px] text-meta text-ink-3 tabular-nums"
        >
          <Icon name="link-2" size={12} />
          {linked === null ? (
            <span className="text-ink-4">{COPY.row.noLinks}</span>
          ) : (
            String(linked)
          )}
        </span>
        <StatusMark row={row} reason={reason} />
      </button>
      <span className="flex w-[34px] flex-none justify-center pr-[6px]">
        {row.status === "received" && (
          <Menu
            label={COPY.row.menu}
            align="end"
            trigger={
              <button
                type="button"
                aria-label={COPY.row.menu}
                className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
              >
                <Icon name="ellipsis" size={14} />
              </button>
            }
            sections={[
              [
                // FIL-01 is N-01 and SHL-21 is K-04 (DV-7): planned links, shown disabled.
                ...(PLANNED_VISIBLE
                  ? [{ label: COPY.row.openInFiles, onSelect: () => undefined, disabled: true }]
                  : []),
                { label: COPY.row.replace, onSelect: () => undefined, disabled: true },
                ...(PLANNED_VISIBLE
                  ? [{ label: COPY.row.unlink, onSelect: () => undefined, disabled: true }]
                  : []),
              ],
            ]}
          />
        )}
      </span>
    </li>
  );
}

function Band({
  group,
  children,
}: {
  group: SourceDocumentGroupOut;
  children: JSX.Element[];
}): JSX.Element {
  if (group.counted === false) {
    // "Sample-driven · 0": not counted in the 24; A-03 populates it after Sample Selection.
    return (
      <section data-aud03-band="sample" aria-label={group.label} className="flex flex-col">
        <div className="flex h-[32px] items-center gap-[8px] bg-nested px-[12px] text-dense font-medium">
          <Icon name="folder" size={13} className="flex-none text-ink-3" />
          <span>{`${group.label} · ${String(group.total)}`}</span>
          {group.total === 0 && (
            <span className="min-w-0 truncate text-meta font-normal text-ink-3">
              {COPY.group.sampleNote}
            </span>
          )}
        </div>
      </section>
    );
  }
  return (
    <SourceDocGroup
      size="compact"
      title={group.label}
      received={group.received}
      total={group.total}
    >
      {children}
    </SourceDocGroup>
  );
}

function moveFocus(event: KeyboardEvent<HTMLDivElement>): void {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const buttons = [
    ...event.currentTarget.querySelectorAll<HTMLButtonElement>("[data-aud03-open]"),
  ];
  const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
  if (at === -1) return;
  const next = buttons[at + (event.key === "ArrowDown" ? 1 : -1)];
  if (next === undefined) return;
  event.preventDefault();
  next.focus();
}

function SourceList({
  docs,
  query,
  selected,
  reasonOf,
  onOpen,
}: {
  docs: SourceDocumentsOut;
  query: string;
  selected: string | null;
  reasonOf: (row: Row) => string | null;
  onOpen: (row: Row) => void;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const q = query.trim().toLowerCase();
  const groups = (docs.groups ?? [])
    .map((g) => ({
      group: g,
      rows: (g.rows ?? []).filter(
        (r) =>
          q === "" ||
          r.title.toLowerCase().includes(q) ||
          (r.latest_upload?.path_label.toLowerCase().includes(q) ?? false),
      ),
    }))
    .filter(({ group, rows }) => q === "" || (group.counted !== false && rows.length > 0));
  if (groups.length === 0) {
    return (
      <EmptyState
        icon="search"
        title={q === "" ? COPY.canvas.empty : COPY.canvas.noMatch(query.trim())}
      />
    );
  }
  return (
    <div data-audit-canvas="source-documents" className="flex flex-col" onKeyDown={moveFocus}>
      {groups.map(({ group, rows }) => (
        <Band key={group.category_id ?? group.label} group={group}>
          {rows.map((row) => (
            <SourceRow
              key={row.request_item_id}
              row={row}
              selected={row.request_item_id === selected}
              reason={reasonOf(row)}
              now={now}
              tz={tz}
              onOpen={onOpen}
            />
          ))}
        </Band>
      ))}
    </div>
  );
}

function canvasState(docs: ReturnType<typeof useSourceDocuments>, retry: () => void): ViewState {
  if (docs.isError) {
    const status = (docs.error as { status?: number } | null)?.status;
    const detail = (docs.error as { detail?: unknown } | null)?.detail;
    return status === 403 || detail === "forbidden"
      ? { kind: "restricted", reason: "role" }
      : { kind: "error", retry };
  }
  if (docs.data === undefined) return { kind: "loading" };
  return { kind: "ready" };
}

// ---- The viewer ----------------------------------------------------------------------------------

/** The verified citation of the screening that lies on this file: lit on open (INV-2). */
function useLitMatch(engagementId: string, row: Row): string | null {
  const card = useScreeningCard(
    row.screening == null ? null : { engagementId, itemId: row.request_item_id },
  );
  const ids = (card.data?.checks ?? []).flatMap((c) => c.citation_ids);
  const citations = useFlagCitations(ids);
  const version = row.latest_upload?.evidence_version_id ?? null;
  const found = Object.values(citations).find(
    (c) => c.verified && c.match_id !== null && c.source.evidence_version_id === version,
  );
  return found?.match_id ?? null;
}

function DecisionStrip({
  row,
  canAccept,
  canReturn,
  accepting,
  onAccept,
  onReturn,
}: {
  row: Row;
  canAccept: boolean;
  canReturn: boolean;
  accepting: boolean;
  onAccept: () => void;
  onReturn: () => void;
}): JSX.Element {
  return (
    <div
      data-decision-strip=""
      className="flex h-[44px] flex-none items-center gap-[8px] px-[12px] hairline-b"
    >
      <span className="flex-1 text-dense text-ink-3">
        {row.match_confidence == null ? null : COPY.strip.match(row.match_confidence)}
      </span>
      {canReturn && (
        <Button variant="secondary" size="sm" opensDialog onClick={onReturn}>
          {COPY.strip.return}
        </Button>
      )}
      {canAccept && (
        <Button variant="primary" size="sm" icon="check" disabled={accepting} onClick={onAccept}>
          {COPY.strip.accept}
        </Button>
      )}
    </div>
  );
}

/** P-04-T42: the AUD-03 entry point into SHL-10. A flagged screening's pending C3 proposal (the
 * card's `proposal_ref`) opens in the approve sheet; the button opens it and decides nothing. */
function ReviewProposal({
  engagementId,
  itemId,
}: {
  engagementId: string;
  itemId: string;
}): JSX.Element | null {
  const card = useScreeningCard({ engagementId, itemId });
  const { open } = useOverlays();
  const ref = card.data?.proposal_ref ?? null;
  if (ref === null) return null;
  return (
    <Button
      variant="secondary"
      size="sm"
      opensDialog
      onClick={() => {
        open("approve", ref);
      }}
    >
      {COPY.reviewProposal}
    </Button>
  );
}

function UploadViewer({
  engagementId,
  row,
  strip,
}: {
  engagementId: string;
  row: Row;
  strip: JSX.Element | null;
}): JSX.Element {
  const lit = useLitMatch(engagementId, row);
  const above = (
    <div className="flex flex-col">
      {strip}
      {row.screening != null && (
        <div className="flex flex-col gap-[8px] p-[10px] pb-0">
          <ScreeningCardHost subject={{ engagementId, itemId: row.request_item_id }} />
          <ReviewProposal engagementId={engagementId} itemId={row.request_item_id} />
        </div>
      )}
    </div>
  );
  return (
    <DockViewer
      versionId={row.latest_upload?.evidence_version_id ?? null}
      above={above}
      lit={lit}
      pageWidth={VIEWER_PAGE}
    />
  );
}

function NotReceived({
  row,
  canRemind,
  canDelegate,
  onRemind,
  onThirdParty,
}: {
  row: Row;
  canRemind: boolean;
  canDelegate: boolean;
  onRemind: () => void;
  onThirdParty: () => void;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const day = (iso: string | null | undefined): string | null =>
    iso == null ? null : date(iso, { now, tz });
  return (
    <div data-not-received="" className="flex min-h-0 flex-1 flex-col justify-center">
      <EmptyState
        icon="file"
        title={COPY.empty.notReceived}
        action={
          <div className="flex items-center gap-[8px]">
            <Button variant="secondary" disabled={!canRemind} onClick={onRemind}>
              {COPY.empty.remind}
            </Button>
            <Button variant="secondary" opensDialog disabled={!canDelegate} onClick={onThirdParty}>
              {COPY.empty.thirdParty}
            </Button>
          </div>
        }
      >
        <span data-requested-line="" className={row.overdue ? "text-red-ink" : undefined}>
          {[
            COPY.empty.requested(
              day(row.requested_at) ?? "",
              row.owed_by?.display ?? null,
              day(row.due_on),
            ),
            ...(row.overdue ? [COPY.empty.overdue] : []),
          ].join(" · ")}
        </span>
      </EmptyState>
    </div>
  );
}

function ThirdPartyDialog({
  engagementId,
  row,
  onClose,
}: {
  engagementId: string;
  row: Row | null;
  onClose: () => void;
}): JSX.Element {
  const contacts = useClientContacts(row === null ? undefined : engagementId);
  const delegation = useDelegate();
  const [picked, setPicked] = useState<string | null>(null);
  const assignee = row?.owed_by?.display ?? null;
  const options = (contacts.data ?? [])
    .filter((c) => (c.display_name ?? c.email ?? "") !== assignee)
    .map((c) => ({ value: c.id, label: c.display_name ?? c.email ?? c.id }));
  const name = options.find((o) => o.value === picked)?.label ?? null;
  const close = (): void => {
    setPicked(null);
    onClose();
  };
  const send = async (): Promise<void> => {
    if (row === null || picked === null || name === null) return;
    try {
      await delegation.delegate(engagementId, row.request_item_id, picked);
      toast.show({ kind: "success", text: COPY.thirdParty.sent(name) });
      close();
    } catch {
      toast.show({ kind: "error", text: COPY.thirdParty.failed });
    }
  };
  return (
    <Dialog
      open={row !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={COPY.thirdParty.title}
      {...(row === null ? {} : { description: row.title })}
      action={
        <Button
          variant="primary"
          disabled={name === null || delegation.delegating}
          onClick={() => void send()}
        >
          {name === null ? COPY.thirdParty.field : COPY.thirdParty.send(name)}
        </Button>
      }
    >
      <div className="flex flex-col gap-[8px]">
        <RadioGroup
          label={COPY.thirdParty.field}
          options={options}
          value={picked ?? ""}
          onChange={setPicked}
        />
        {name !== null && assignee !== null && (
          <p className="text-meta text-ink-3">{COPY.thirdParty.help(name, assignee)}</p>
        )}
      </div>
    </Dialog>
  );
}

// ---- The screen ----------------------------------------------------------------------------------

function Screen({
  cockpit,
  item,
  onItem,
  sort,
  onSort,
  q,
  onQuery,
  returning: openReturn,
  onBack,
  onSection,
  onAdd,
  embedded,
}: Omit<AUD03Props, "auditId"> & { cockpit: AuditCockpitOut }): JSX.Element {
  const engagementId = cockpit.engagement_id;
  const [ownQuery, setOwnQuery] = useState(q ?? "");
  const [ownSort, setOwnSort] = useState<Sort>(sort ?? "missing_first");
  const [ownItem, setOwnItem] = useState<string | null>(item ?? null);
  const query = q ?? ownQuery;
  const order = sort ?? ownSort;
  const current = item === undefined ? ownItem : item;
  const docs = useSourceDocuments(cockpit.work_item_id, order, { poll: LIVE_POLL_MS });
  const agent = useAgentTab(engagementId);
  const decisions = useSourceDocumentDecisions();
  const person = useSession({ engagementId }).user?.displayName ?? "";
  const canAccept = useCan("evidence.accept", { engagementId });
  const canReturn = useCan("evidence.reject", { engagementId });
  const canRemind = useCan("follow_up.draft", { engagementId });
  const canDelegate = useCan("request_item.delegate", { engagementId });
  const reasons = useQuery({
    ...reasonCodesOptions({ path: { engagement_id: engagementId, applies_to: "send_back" } }),
    retry: false,
  });
  const [dock, setDock] = useState<"agent" | "viewer">("viewer");
  const [remind, setRemind] = useState<FollowUpSelection | null>(null);
  const [returning, setReturning] = useState<ReturnTarget | null>(null);
  const [thirdParty, setThirdParty] = useState<Row | null>(null);
  const [opened, setOpened] = useState(false);

  const rows = useMemo(() => (docs.data?.groups ?? []).flatMap((g) => g.rows ?? []), [docs.data]);
  const selected = rows.find((r) => r.request_item_id === current) ?? null;
  const open = rows.filter(isOpen);
  const nothingMissing = docs.data !== undefined && rows.length > 0 && open.length === 0;

  const reasonOf = (row: Row): string | null => {
    if (row.returned_reason == null) return null;
    const label = (reasons.data ?? []).find((r) => r.code === row.returned_reason)?.label;
    const words = label ?? row.returned_reason.replace(/_/g, " ");
    return words.charAt(0).toLowerCase() + words.slice(1);
  };
  const select = (row: Row): void => {
    setOwnItem(row.request_item_id);
    onItem?.(row.request_item_id);
    setDock("viewer");
  };
  const returnTarget = (row: Row, reason?: string): ReturnTarget | null => {
    const upload = row.latest_upload ?? null;
    if (upload === null) return null;
    return {
      engagementId,
      versionId: upload.evidence_version_id,
      fileName: fileName(upload.path_label),
      ...(reason === undefined ? {} : { reason }),
    };
  };
  // d: the artboard opens with "Return…" pressed (Wrong document preselected, the flag's reason).
  useEffect(() => {
    if (openReturn !== true || opened || selected?.status !== "uploaded") return;
    setOpened(true);
    setReturning(returnTarget(selected, "wrong_document"));
  }, [openReturn, opened, selected]);

  const accept = async (row: Row): Promise<void> => {
    const version = row.latest_upload?.evidence_version_id;
    if (version === undefined) return;
    try {
      await decisions.accept(engagementId, version);
      toast.show({ kind: "success", text: COPY.strip.accepted(row.title) });
    } catch {
      toast.show({ kind: "error", text: COPY.strip.failed });
    }
  };
  const remindOwner = (row: Row): void => {
    const owner = row.owed_by?.display ?? null;
    const ids = open
      .filter((r) => owner === null || r.owed_by?.display === owner)
      .map((r) => r.request_item_id);
    setRemind({ kind: "requests", requestItemIds: ids.length > 0 ? ids : [row.request_item_id] });
  };

  const state = canvasState(docs, () => void docs.refetch());
  const binderId = rows[0]?.binder_id;
  const canvas: CockpitCanvas = {
    title: COPY.canvas.title,
    actions: (
      <>
        {onAdd !== undefined && binderId !== undefined && (
          <PaneAction
            icon="file-plus"
            label={COPY.canvas.add}
            onClick={() => {
              onAdd(binderId);
            }}
          />
        )}
        <PaneAction kind="icon" icon="list-filter" label={COPY.canvas.filter} />
        {canRemind && (
          <PaneAction
            icon="bell"
            label={COPY.canvas.remind}
            opensDialog
            disabled={open.length === 0}
            onClick={() => {
              setRemind({ kind: "requests", requestItemIds: open.map((r) => r.request_item_id) });
            }}
          />
        )}
      </>
    ),
    controls: (
      <>
        <SearchField
          label={COPY.canvas.search}
          placeholder={COPY.canvas.search}
          value={query}
          onChange={(next) => {
            setOwnQuery(next);
            onQuery?.(next);
          }}
          className="min-w-0 flex-1"
        />
        <Button
          variant="secondary"
          size="sm"
          icon="arrow-up-down"
          disabled={nothingMissing}
          aria-pressed={order === "missing_first"}
          onClick={() => {
            const next = order === "missing_first" ? "received_first" : "missing_first";
            setOwnSort(next);
            onSort?.(next);
          }}
        >
          {nothingMissing
            ? COPY.canvas.nothingMissing
            : order === "missing_first"
              ? COPY.canvas.missingFirst
              : COPY.canvas.receivedFirst}
        </Button>
      </>
    ),
    children: (
      <ViewStateBody state={state} rows="list" empty={{ title: COPY.canvas.empty }}>
        {() =>
          docs.data === undefined ? null : (
            <SourceList
              docs={docs.data}
              query={query}
              selected={current}
              reasonOf={reasonOf}
              onOpen={select}
            />
          )
        }
      </ViewStateBody>
    ),
  };

  let viewer: JSX.Element;
  if (selected === null) {
    viewer = <DockViewer versionId={null} />;
  } else if (selected.latest_upload == null || selected.status === "returned") {
    viewer = (
      <NotReceived
        row={selected}
        canRemind={canRemind}
        canDelegate={canDelegate}
        onRemind={() => {
          remindOwner(selected);
        }}
        onThirdParty={() => {
          setThirdParty(selected);
        }}
      />
    );
  } else {
    const strip =
      selected.status === "uploaded" && (canAccept || canReturn) ? (
        <DecisionStrip
          row={selected}
          canAccept={canAccept}
          canReturn={canReturn}
          accepting={decisions.accepting}
          onAccept={() => void accept(selected)}
          onReturn={() => {
            setReturning(
              returnTarget(
                selected,
                selected.screening === "flagged" ? "wrong_document" : undefined,
              ),
            );
          }}
        />
      ) : null;
    viewer = (
      <UploadViewer
        key={selected.request_item_id}
        engagementId={engagementId}
        row={selected}
        strip={strip}
      />
    );
  }

  return (
    <div data-screen="AUD-03" className="flex min-h-0 flex-1 flex-col [--dock-w:var(--ev-w)]">
      <AuditCockpit
        cockpit={cockpit}
        canvas={canvas}
        section={SOURCE_DOCUMENTS}
        onSection={(r) => {
          if (r.key !== SOURCE_DOCUMENTS) onSection?.(r.key);
        }}
        bar={onBack === undefined ? {} : { onBack }}
        dock={{
          tab: dock,
          onTab: setDock,
          agent: (
            <AgentDock engagementId={engagementId}>
              <AgentActivityTab engagementId={engagementId} />
            </AgentDock>
          ),
          viewer,
          aiUnavailable: agent.aiUnavailable,
        }}
        {...(embedded === undefined ? {} : { embedded })}
      />
      <ReturnDialog
        target={returning}
        onClose={() => {
          setReturning(null);
        }}
        onReturned={() => {
          decisions.refresh();
        }}
      />
      <FollowUpSheet
        selection={remind}
        person={person}
        onClose={() => {
          setRemind(null);
        }}
      />
      <ThirdPartyDialog
        engagementId={engagementId}
        row={thirdParty}
        onClose={() => {
          setThirdParty(null);
        }}
      />
    </div>
  );
}

export function AUD03({ auditId, ...rest }: AUD03Props): JSX.Element {
  const cockpit = useAuditCockpit(auditId);
  if (cockpit.isError) {
    // Outside the tenant, behind a wall or not assurance: a 404 with no hint it exists (INV-3).
    const state: ViewState = isNotFound(cockpit.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void cockpit.refetch() };
    return (
      <div data-screen="AUD-03" className="flex min-h-0 flex-1 flex-col">
        <ViewStateBody state={state} empty={{ title: COPY.notFound }} noun="audit">
          {() => null}
        </ViewStateBody>
      </div>
    );
  }
  if (cockpit.data === undefined) {
    return (
      <div data-screen="AUD-03" className="flex min-h-0 flex-1 flex-col">
        <ViewStateBody state={{ kind: "loading" }} rows="list" empty={{ title: COPY.notFound }}>
          {() => null}
        </ViewStateBody>
      </div>
    );
  }
  return <Screen cockpit={cockpit.data} {...rest} />;
}

/** The gallery's artboard and the tests' page: AUD-03 with its own URL-shaped state. */
export function SourceDocumentsPage({
  auditId,
  initial = {},
  onBack,
}: {
  auditId: string;
  initial?: { item?: string | null; returning?: boolean };
  onBack?: () => void;
}): JSX.Element {
  const [item, setItem] = useState<string | null>(initial.item ?? null);
  return (
    <AUD03
      auditId={auditId}
      item={item}
      onItem={setItem}
      {...(initial.returning === undefined ? {} : { returning: initial.returning })}
      {...(onBack === undefined ? {} : { onBack })}
    />
  );
}
