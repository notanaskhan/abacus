import type {
  AuditCockpitOut,
  AuditSectionRowOut,
  SourceDocumentRowOut,
  SourceDocumentsOut,
} from "@abacus/api-client";
import {
  Button,
  type CockpitCanvas,
  ConfirmDialog,
  EmptyState,
  PaneAction,
  type SourceDoc,
  SourceDocGroup,
  SourceDocRow,
  SearchField,
  ViewStateBody,
  type ViewState,
} from "@abacus/ui";
import { type JSX, useRef, useState } from "react";
import {
  AgentActivityTab,
  AgentDockMenu,
  AuditCockpit,
  type AuditOverlay,
  type AutoModeStep,
  BlockedSectionCard,
  DockViewer,
  isNotFound,
  useAgentTab,
  useAuditActions,
  useAuditCockpit,
  useAutoMode,
  useSourceDocuments,
} from "../../domain/audits";
import { useFlag } from "../../app-core/flags";
import { AgentDock } from "../../domain/agents";
import { type TrialBalanceOptions, useTrialBalancePane } from "../AUD-06/TrialBalance";
import { ViewerPane } from "../SHL-08";
import { COPY } from "./copy";

// AUD-02 · Audit cockpit (A-01-T12; docs/screens/AUD-02.md): F-05's T2 RecordCockpit through the
// A-01-T06 L3 (audit bar, registered rail, dock host) with the Source Documents canvas, the Viewer
// dock tab (SHL-08 on `?doc=`) and the read-only v1 Agent tab with "Pause agent" and DF-04's state.
// Each artboard is its data (fixtures/scenarios/AUD-02.ts):
//
//   a  Marcus Delaney's run #4127 at 9:41 AM: the run grammar ("Complete · 9:26 AM" … "Begin…")
//   b  no run, 9:20 AM: every phase "Not started", the overview pill "Planning"
//   c  the plan proposed, 9:23 AM: rail as b (the proposal card is P-09's dock)
//   d  `?section=materiality` blocked on Margaret Okonkwo: the BlockedSectionCard
//   e  9:58 AM: Internal Control "Failed — see run"
//   f  Auto mode pressed: the O3 confirm (A-01-T31), and the server's refusal for a real firm
//   g  no run, the audit-program grammar: "Ready" / "In progress" pills
//
// a, c, d and e draw the rail and canvas from fixtures; their dock (RunCard, transcript, plan
// approval, Retry) is P-09 on P-10 and is masked in parity. f is fixture only until P-10-T39 serves
// `PUT /v1/engagements/{id}/auto-mode` and reports `engagement_run.auto_mode` (DEC-405); h (Group
// band) is A-09's; i (Board) K-04's. No Run, Begin…, Sign off run or Auto mode control renders
// without its capability (A-01 Story 2.1).

export type DockTab = "agent" | "viewer";

export interface AUD02Props {
  /** The assurance work item (`$auditId`). */
  auditId: string;
  /** The selected rail row (`?section=`); Source Documents by default. */
  section?: string;
  onSection?: (key: string) => void;
  /** The dock tab (`?dock=`) and the document open in the Viewer (`?doc=`). */
  dock?: DockTab;
  doc?: string | null;
  onDock?: (tab: DockTab, doc?: string | null) => void;
  /** "All Audits" (AUD-01). */
  onBack?: () => void;
  /** "Add": the SHL-14 composer over the work item's PBC binder (`?ov=request:new:<binderId>`). */
  onAdd?: (binderId: string) => void;
  /** Inside the firm shell (a routed screen) the toolbar is the shell's. */
  embedded?: boolean;
  /** What the Trial Balance row's AUD-06 pane opens on (tab, layer, selected line). */
  trialBalance?: TrialBalanceOptions["initial"];
  /** The Auto mode confirm's opening step (AUD-02 f opens it asking). */
  autoMode?: AutoModeStep;
  /** `?ov=export[:<id>]` or a record dialog (A-01-T24): the overlay it opens on. */
  overlay?: AuditOverlay;
  onOverlay?: (overlay: AuditOverlay) => void;
}

/** The rail row whose canvas is AUD-06 (A-02-T09). */
const TRIAL_BALANCE = "trial_balance";

type Sort = "missing_first" | "received_first";

function docOf(row: SourceDocumentRowOut): SourceDoc {
  const status =
    row.status === "received" ? "received" : row.status === "uploaded" ? "review" : "requested";
  return {
    id: row.request_item_id,
    title: row.title,
    ...(row.latest_upload == null ? {} : { path: row.latest_upload.path_label }),
    status,
  };
}

function SourceDocuments({
  docs,
  query,
  open,
  onOpen,
}: {
  docs: SourceDocumentsOut;
  query: string;
  open: string | null;
  onOpen: (row: SourceDocumentRowOut) => void;
}): JSX.Element {
  const q = query.trim().toLowerCase();
  const groups = (docs.groups ?? [])
    .map((g) => ({
      ...g,
      shown: (g.rows ?? []).filter((r) => q === "" || r.title.toLowerCase().includes(q)),
    }))
    .filter((g) => q === "" || g.shown.length > 0);
  if (groups.length === 0) {
    return (
      <EmptyState
        icon="search"
        title={q === "" ? COPY.canvas.empty : COPY.canvas.noMatch(query.trim())}
      />
    );
  }
  return (
    <div data-audit-canvas="source-documents" className="flex flex-col">
      {groups.map((g) => (
        <SourceDocGroup key={g.category_id} title={g.label} received={g.received} total={g.total}>
          {g.shown.map((row) => (
            <SourceDocRow
              key={row.request_item_id}
              doc={docOf(row)}
              selected={open !== null && row.latest_upload?.evidence_version_id === open}
              onOpen={() => {
                onOpen(row);
              }}
            />
          ))}
        </SourceDocGroup>
      ))}
    </div>
  );
}

function canvasState(docs: ReturnType<typeof useSourceDocuments>, ready: () => void): ViewState {
  if (docs.isError) {
    // A metadata-only reader (firm admin, client service) may not read the requests (ADR-024).
    const status = (docs.error as { status?: number } | null)?.status;
    const detail = (docs.error as { detail?: unknown } | null)?.detail;
    return status === 403 || detail === "forbidden"
      ? { kind: "restricted", reason: "role" }
      : { kind: "error", retry: ready };
  }
  if (docs.data === undefined) return { kind: "loading" };
  return { kind: "ready" };
}

function Cockpit({
  cockpit,
  section,
  onSection,
  dock,
  doc,
  onDock,
  onBack,
  onAdd,
  embedded,
  trialBalance,
  autoMode: autoModeStep,
  overlay,
  onOverlay,
}: Omit<AUD02Props, "auditId"> & { cockpit: AuditCockpitOut }): JSX.Element {
  // A-01-T24: "Export binder…" and the record-mode entries (DV-9, DV-4).
  const audit = useAuditActions(cockpit, overlay ?? null, onOverlay);
  const [query, setQuery] = useState("");
  // AUD-02 f (A-01-T31): the switch renders only with `engagement_run.auto_mode` from `/v1/me`.
  const autoMode = useAutoMode(cockpit, autoModeStep);
  // The kit's confirm closes itself after Turn on; the write decides whether it stays open.
  const confirming = useRef(false);
  const [sort, setSort] = useState<Sort>("missing_first");
  const docs = useSourceDocuments(cockpit.work_item_id, sort);
  const agent = useAgentTab(cockpit.engagement_id);
  const selected = section ?? "source_documents";
  const rows = (cockpit.bands ?? []).flatMap((b) => b.rows ?? []);
  const row: AuditSectionRowOut | undefined = rows.find((r) => r.key === selected);
  // AUD-06 (A-02-T09): the Trial Balance row's workpaper; a line's citation re-targets the Viewer.
  // Behind `ledger.tb_workpaper` (DEC-314): the C9 v1 view is a stub until A-02-T10.
  const tbOn = useFlag("ledger.tb_workpaper") === true && selected === TRIAL_BALANCE;
  const tb = useTrialBalancePane(cockpit.engagement_id, {
    enabled: tbOn,
    ...(trialBalance === undefined ? {} : { initial: trialBalance }),
    onLink: () => {
      onDock?.("viewer", doc ?? null);
    },
  });
  const openDoc = (r: SourceDocumentRowOut): void => {
    const version = r.latest_upload?.evidence_version_id ?? null;
    if (version !== null) onDock?.("viewer", version);
  };

  let canvas: CockpitCanvas;
  if (tbOn) {
    canvas = tb.canvas;
  } else if (row?.section_state === "blocked_on_decision" && row.blocked_on_name != null) {
    canvas = {
      title: row.title,
      children: (
        <BlockedSectionCard person={row.blocked_on_name} body={COPY.blocked[row.key] ?? ""} />
      ),
    };
  } else {
    const state = canvasState(docs, () => void docs.refetch());
    const binderId = docs.data?.groups?.[0]?.rows?.[0]?.binder_id;
    canvas = {
      title: COPY.canvas.title,
      actions: (
        <>
          <PaneAction kind="icon" icon="list-filter" label={COPY.canvas.filter} />
          {audit.menu}
          {onAdd !== undefined && binderId !== undefined && (
            <PaneAction
              icon="file-plus"
              label={COPY.canvas.add}
              onClick={() => {
                onAdd(binderId);
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
            onChange={setQuery}
            className="min-w-0 flex-1"
          />
          <Button
            variant="secondary"
            size="sm"
            icon="list-filter"
            aria-pressed={sort === "missing_first"}
            onClick={() => {
              setSort(sort === "missing_first" ? "received_first" : "missing_first");
            }}
          >
            {sort === "missing_first" ? COPY.canvas.missingFirst : COPY.canvas.receivedFirst}
          </Button>
        </>
      ),
      children: (
        <ViewStateBody state={state} rows="list" empty={{ title: COPY.canvas.empty }}>
          {() =>
            docs.data === undefined ? null : (
              <SourceDocuments
                docs={docs.data}
                query={query}
                open={doc ?? null}
                onOpen={openDoc}
              />
            )
          }
        </ViewStateBody>
      ),
    };
  }

  const pausable = (cockpit.allowed_actions ?? []).includes("agent.pause");
  return (
    <div data-screen="AUD-02" className="flex min-h-0 flex-1 flex-col">
      <AuditCockpit
        cockpit={cockpit}
        canvas={canvas}
        section={selected}
        onSection={(r) => {
          onSection?.(r.key);
        }}
        bar={{
          ...(onBack === undefined ? {} : { onBack }),
          autoMode: autoMode.allowed ? autoMode.on : null,
          onAutoMode: autoMode.press,
        }}
        dock={{
          tab: dock ?? "agent",
          onTab: (tab) => {
            onDock?.(tab, doc ?? null);
          },
          // P-09-T09: the SHL-13 run pane, with the v1 activity list below its thread.
          agent: (
            <AgentDock engagementId={cockpit.engagement_id}>
              <AgentActivityTab engagementId={cockpit.engagement_id} />
            </AgentDock>
          ),
          viewer:
            tbOn && tb.linked !== null ? (
              <ViewerPane target={tb.linked} />
            ) : (
              <DockViewer versionId={doc ?? null} />
            ),
          aiUnavailable: agent.aiUnavailable,
          ...(pausable ? { action: <AgentDockMenu engagementId={cockpit.engagement_id} /> } : {}),
        }}
        {...(embedded === undefined ? {} : { embedded })}
      />
      {audit.overlays}
      <ConfirmDialog
        open={autoMode.allowed && autoMode.step !== "idle"}
        onOpenChange={(open) => {
          if (open) return;
          if (confirming.current) {
            confirming.current = false;
            return;
          }
          autoMode.cancel();
        }}
        title={COPY.autoMode.title}
        confirmLabel={COPY.autoMode.confirm}
        cancelLabel={COPY.autoMode.cancel}
        destructive={false}
        onConfirm={() => {
          confirming.current = true;
          if (!autoMode.saving) autoMode.confirm();
        }}
      >
        {autoMode.step === "refused" ? (
          <span role="alert" data-auto-mode="refused">
            {COPY.autoMode.refused}
          </span>
        ) : (
          COPY.autoMode.body
        )}
      </ConfirmDialog>
    </div>
  );
}

export function AUD02({ auditId, ...rest }: AUD02Props): JSX.Element {
  const cockpit = useAuditCockpit(auditId);
  if (cockpit.isError) {
    // Outside the tenant, behind a wall or not assurance: a 404 with no hint it exists (INV-3).
    const state: ViewState = isNotFound(cockpit.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void cockpit.refetch() };
    return (
      <div data-screen="AUD-02" className="flex min-h-0 flex-1 flex-col">
        <ViewStateBody state={state} empty={{ title: COPY.notFound }} noun="audit">
          {() => null}
        </ViewStateBody>
      </div>
    );
  }
  if (cockpit.data === undefined) {
    return (
      <div data-screen="AUD-02" className="flex min-h-0 flex-1 flex-col">
        <ViewStateBody state={{ kind: "loading" }} rows="list" empty={{ title: COPY.notFound }}>
          {() => null}
        </ViewStateBody>
      </div>
    );
  }
  return <Cockpit cockpit={cockpit.data} {...rest} />;
}

/** The routed page and the gallery's artboard with their own dock state. */
export function AuditCockpitPage({
  auditId,
  initial = {},
  onBack,
}: {
  auditId: string;
  initial?: {
    section?: string;
    dock?: DockTab;
    doc?: string | null;
    trialBalance?: TrialBalanceOptions["initial"];
    autoMode?: AutoModeStep;
    overlay?: AuditOverlay;
  };
  onBack?: () => void;
}): JSX.Element {
  const [section, setSection] = useState(initial.section);
  const [dock, setDock] = useState<DockTab>(initial.dock ?? "agent");
  const [doc, setDoc] = useState<string | null>(initial.doc ?? null);
  return (
    <AUD02
      auditId={auditId}
      {...(section === undefined ? {} : { section })}
      onSection={setSection}
      dock={dock}
      doc={doc}
      onDock={(tab, next) => {
        setDock(tab);
        if (next !== undefined) setDoc(next);
      }}
      {...(onBack === undefined ? {} : { onBack })}
      {...(initial.trialBalance === undefined ? {} : { trialBalance: initial.trialBalance })}
      {...(initial.autoMode === undefined ? {} : { autoMode: initial.autoMode })}
      {...(initial.overlay === undefined ? {} : { overlay: initial.overlay })}
    />
  );
}
