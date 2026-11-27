// SHT-01 e · the row drawer (K-03-T22; TASK-9028; DEC-6033): the O2 480 drawer over the sheet at
// `?ov=row:<rowKey>`, so it deep-links, survives a reload and closes on Back (F-05-T20). It reads
// `GET /v1/sheets/{sid}/rows/{rid}` (the row's facts in column order, the agent's reason for each
// suggested cell, the row's links) and draws six tabs: Details with the Why card, Comments (C-29
// on the row's anchor), Agents (the run that made the suggestion), Evidence, Requests and To-dos
// (C-30). The agent's reason is agent text (AgentText); its sources are the cell's anchor's
// citation stack, each chip opening SHL-07. "Adopt (L1)" opens SHL-12 at L1 for this row: a
// preparer's sign-off adopts the row's suggestions (SHT-01 spec), never the drawer itself.
// "Raise exception…" opens AUD-15. Nothing here adopts, signs or raises on its own (INV-1).
import type { CitationV2Out, SheetRowDetailOut } from "@abacus/api-client";
import {
  agentRunOptions,
  listCitationsOptions,
  listTodosOptions,
  sheetRowDetailOptions,
  sheetRowsOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  Drawer,
  DrawerCard,
  Icon,
  MatchScope,
  Segmented,
  Skeleton,
  amount,
  date,
  time,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { type JSX, type ReactNode, useState } from "react";
import { useNow, useToday } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { useSession } from "../../app-core/session";
import { LiveCommentThread, ToDoRow } from "../../domain/collaboration";
import { ov, to } from "../../routes/to";
import { CitationPopoverContainer, CitedCell } from "../SHL-07";
import { COPY as C } from "./copy";

/** The column whose suggestion the Why card explains and Adopt (L1) adopts. */
const CONCLUSION = "conclusion";

type Fact = NonNullable<SheetRowDetailOut["facts"]>[number];

function shown(fact: Fact, now: Date): string {
  if (fact.value === "") return "—";
  if (fact.type === "currency" || fact.type === "number") {
    return amount(fact.value, fact.type === "currency" ? "cents" : "whole").text;
  }
  if (fact.type === "date") return date(fact.value, { now, withYear: true });
  return fact.value;
}

function Kv({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[33px] items-center justify-between gap-[12px] px-[14px] hairline-b last:shadow-none">
      <dt className="text-[12.5px] text-ink-2">{k}</dt>
      <dd className="text-right text-[12.5px]">{children}</dd>
    </div>
  );
}

function ConclusionChip({ value, suggested }: { value: string; suggested: boolean }): JSX.Element {
  const labels: Readonly<Record<string, string | undefined>> = C.conclusion;
  const label = labels[value] ?? value;
  const exception = value === "improperly_excluded";
  return (
    <span className="inline-flex items-center gap-[6px]" data-sht01="conclusion">
      <span
        className={
          exception
            ? "inline-flex h-[20px] items-center rounded-pill bg-red-tint px-[8px] text-[12px] font-medium text-red-ink"
            : "inline-flex h-[20px] items-center rounded-pill bg-nested px-[8px] text-[12px] text-ink-2"
        }
      >
        {label}
      </span>
      {suggested ? (
        <Icon name="atom" size={12} className="text-ink-3" label={C.drawer.suggestedAtom} />
      ) : null}
    </span>
  );
}

function Details({
  detail,
  citations,
}: {
  detail: SheetRowDetailOut;
  citations: readonly CitationV2Out[];
}): JSX.Element {
  const now = useNow();
  const cell = detail.row.cells[CONCLUSION];
  const why = (detail.why ?? []).find((w) => w.column_key === CONCLUSION);
  return (
    <>
      <DrawerCard data-sht01="details">
        <dl>
          {(detail.facts ?? []).map((f) => (
            <Kv key={f.label} k={f.label}>
              {shown(f, now)}
            </Kv>
          ))}
          {cell !== undefined && cell.value !== "" ? (
            <Kv k={C.drawer.conclusion}>
              <ConclusionChip value={cell.value} suggested={cell.state === "suggested"} />
            </Kv>
          ) : null}
        </dl>
      </DrawerCard>
      {why?.rationale ? (
        <DrawerCard data-sht01="why" className="flex flex-col gap-[10px] p-[14px]">
          <h3 className="text-[13px] font-medium">{C.drawer.why}</h3>
          <AgentText text={why.rationale} className="text-[12.5px] leading-[1.55] text-ink" />
          {citations.length > 0 ? (
            <div className="flex flex-wrap gap-[6px]" data-sht01="citations">
              {citations.map((c) => (
                <CitedCell
                  key={c.id}
                  as="button"
                  citations={[c]}
                  className="inline-flex h-[24px] items-center gap-[5px] rounded-pill bg-card px-[9px] text-[12px] shadow-e1"
                >
                  <Icon name="file-text" size={12} />
                  {`${c.title} · ${c.loc}`}
                </CitedCell>
              ))}
            </div>
          ) : null}
        </DrawerCard>
      ) : null}
    </>
  );
}

function AgentsTab({ runId }: { runId: string | null }): JSX.Element {
  const now = useNow();
  const run = useQuery({
    ...agentRunOptions({ path: { run_id: runId ?? "" } }),
    enabled: runId !== null,
  });
  if (runId === null) return <p className="p-[14px] text-[12.5px] text-ink-3">{C.drawer.noAgents}</p>;
  if (run.data === undefined) return <Skeleton className="m-[10px] h-[60px]" />;
  const finished = run.data.run.finished_at;
  return (
    <DrawerCard className="p-[14px]" data-sht01="agent">
      <p className="text-[12.5px]">
        {run.data.run.agent_label}
        {finished !== null
          ? ` · ${C.drawer.finished(date(finished, { now }), time(finished))}`
          : ""}
      </p>
    </DrawerCard>
  );
}

function LinksTab({
  links,
  kind,
  empty,
}: {
  links: SheetRowDetailOut["links"];
  kind: "evidence" | "request";
  empty: string;
}): JSX.Element {
  const now = useNow();
  const mine = (links ?? []).filter((l) => l.kind === kind);
  if (mine.length === 0) return <p className="p-[14px] text-[12.5px] text-ink-3">{empty}</p>;
  return (
    <DrawerCard data-sht01={kind}>
      <ul>
        {mine.map((l) => (
          <li key={l.target_id} className="flex min-h-[33px] items-center justify-between px-[14px] hairline-b last:shadow-none">
            <span className="text-[12.5px]">{l.label ?? C.drawer.linkKind[kind]}</span>
            <span className="text-[12px] text-ink-3">
              {C.drawer.linked(date(l.linked_at, { now }))}
            </span>
          </li>
        ))}
      </ul>
    </DrawerCard>
  );
}

function TodosTab({ rowId }: { rowId: string }): JSX.Element {
  const today = useToday();
  const todos = useQuery(
    listTodosOptions({ query: { anchor_kind: "sheet_row", anchor_id: rowId } }),
  );
  const items = todos.data?.items ?? [];
  if (todos.isPending) return <Skeleton className="m-[10px] h-[60px]" />;
  if (items.length === 0) {
    return <p className="p-[14px] text-[12.5px] text-ink-3">{C.drawer.noTodos}</p>;
  }
  return (
    <DrawerCard>
      {items.map((t) => (
        <ToDoRow key={t.id} todo={t} today={today} />
      ))}
    </DrawerCard>
  );
}

export interface RowDrawerProps {
  sheetId: string;
  auditId: string | undefined;
  rowKey: string;
  onClose: () => void;
}

export function RowDrawer({ sheetId, auditId, rowKey, onClose }: RowDrawerProps): JSX.Element {
  const openOverlay = useOpenOverlay();
  const navigate = useNavigate();
  const viewerId = useSession().user?.id ?? "";
  const [tab, setTab] = useState<string>(C.drawer.tabs.details);
  const rows = useQuery(sheetRowsOptions({ path: { sheet_id: sheetId } }));
  const row = rows.data?.items.find((r) => r.key === rowKey);
  const detail = useQuery({
    ...sheetRowDetailOptions({ path: { sheet_id: sheetId, row_id: row?.row_id ?? "" } }),
    enabled: row !== undefined,
  });
  const citations = useQuery({
    ...listCitationsOptions({
      query: { anchor_type: "sheet_row", anchor_id: row?.row_id ?? "", anchor_ref: CONCLUSION },
    }),
    enabled: row !== undefined,
  });
  const d = detail.data;
  const vendor = d?.row.cells["vendor"]?.value ?? row?.cells["vendor"]?.value;
  const title = vendor ? `${rowKey} · ${vendor}` : rowKey;
  const why = (d?.why ?? []).find((w) => w.column_key === CONCLUSION);
  const locked = d?.row.locked ?? row?.locked ?? false;
  const exception = d?.row.cells[CONCLUSION]?.exception === true;
  const footer =
    d === undefined || locked ? undefined : (
      <div className="flex justify-end gap-[8px]">
        <Button
          variant="secondary"
          size="sm"
          disabled={auditId === undefined || !exception}
          onClick={() => {
            if (auditId !== undefined) void navigate(to.AUD15({ auditId }));
          }}
        >
          {C.drawer.raiseException}
        </Button>
        <Button
          variant="primary"
          size="sm"
          disabled={why === undefined || why.status !== "pending"}
          onClick={() => {
            openOverlay(ov.SHL12("sheet_row", d.row.row_id, "L1"));
          }}
        >
          {C.drawer.adopt}
        </Button>
      </div>
    );
  const T = C.drawer.tabs;
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={title}
      width={480}
      bare
      {...(footer === undefined ? {} : { footer })}
    >
      <MatchScope>
        <div className="px-[10px] pt-[10px]">
          <Segmented
            size="small"
            label={C.drawer.tabsLabel}
            options={[T.details, T.comments, T.agents, T.evidence, T.requests, T.todos]}
            active={tab}
            onChange={setTab}
          />
        </div>
        {d === undefined ? (
          detail.isError || (rows.isSuccess && row === undefined) ? (
            <p role="alert" className="p-[14px] text-[12.5px]">
              {C.drawer.notFound}
            </p>
          ) : (
            <Skeleton className="m-[10px] h-[300px]" />
          )
        ) : tab === T.details ? (
          <Details detail={d} citations={citations.data?.items ?? []} />
        ) : tab === T.comments ? (
          <div className="p-[10px]">
            <LiveCommentThread
              variant="drawer"
              anchor={{ anchor_kind: "sheet_row", anchor_id: d.row.row_id }}
              anchorLabel={title}
              engagementId={d.engagement_id}
              engagementLabel={title}
              viewerId={viewerId}
            />
          </div>
        ) : tab === T.agents ? (
          <AgentsTab runId={why?.agent_run_id ?? null} />
        ) : tab === T.evidence ? (
          <LinksTab links={d.links} kind="evidence" empty={C.drawer.noEvidence} />
        ) : tab === T.requests ? (
          <LinksTab links={d.links} kind="request" empty={C.drawer.noRequests} />
        ) : (
          <TodosTab rowId={d.row.row_id} />
        )}
        <CitationPopoverContainer />
      </MatchScope>
    </Drawer>
  );
}

/** The `?ov=row:<rowKey>` layer: the sheet and audit come from the route under it. */
export function RowDrawerLayer({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const params: { sheetId?: string; auditId?: string } = useParams({ strict: false });
  const rowKey = ref.args[0];
  if (rowKey === undefined || params.sheetId === undefined) return null;
  return (
    <RowDrawer sheetId={params.sheetId} auditId={params.auditId} rowKey={rowKey} onClose={close} />
  );
}
