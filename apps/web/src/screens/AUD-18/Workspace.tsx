import type {
  EqrChecklistItemOut,
  EqrDigestCardOut,
  EqrNoteRowOut,
  EqrReviewOut,
} from "@abacus/api-client";
import {
  eqrCardReviewedMutation,
  eqrConcurMutation,
  eqrReviewOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  Pill,
  Segmented,
  Skeleton,
  StatusDisc,
  ViewStateBody,
  type ViewState,
  cn,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { AuditBar, isNotFound, useAuditCockpit } from "../../domain/audits";
import { hrefOf, to } from "../../routes/to";
import { COPY } from "./copy";

// AUD-18 · EQR workspace (A-07-T17; A-07 F1; the handoff spec) in fixture mode on T2: rail checklist
// 330, digest canvas 696, dock 330 with Notes · Agent. The reviewer reads; there's no Edit and no
// L1 to L4 here. Concurrence is the assigned EQR's alone, with an attestation and a fresh second
// factor, and it's never optimistic. The agent builds the digest and evaluates nothing (INV-1).

const PANE = "flex min-h-0 flex-col overflow-hidden rounded-[12px] bg-card e2";
const HEADER =
  "flex h-[46px] shrink-0 items-center justify-between px-[12px] text-[14.5px] font-medium";

type Dock = "notes" | "agent";

export interface EqrWorkspaceProps {
  auditId: string;
  dock?: Dock;
  /** The Concur… sheet (b2) starts open. */
  concurring?: boolean;
  onBack?: () => void;
  onSourceDocs?: () => void;
  /** A citation chip opens the cited screen read-only. */
  onCited?: (target: string) => void;
}

const DISC = { todo: "todo", partial: "half", done: "done" } as const;

function Row({ item }: { item: EqrChecklistItemOut }): JSX.Element {
  return (
    <div
      data-checklist={item.item_key}
      data-status={item.status}
      className="flex min-h-[38px] items-center gap-[8px] px-[12px]"
    >
      <StatusDisc state={DISC[item.status]} size={15} />
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-[12.5px]">{item.title}</span>
        {item.sub_line != null && (
          <span className="truncate text-[11.5px] text-ink-3">{item.sub_line}</span>
        )}
      </span>
    </div>
  );
}

function Card({
  card,
  canMark,
  auditId,
  onCited,
}: {
  card: EqrDigestCardOut;
  canMark: boolean;
  auditId: string;
  onCited: ((target: string) => void) | undefined;
}): JSX.Element {
  const client = useQueryClient();
  const mark = useMutation({
    ...eqrCardReviewedMutation(),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: eqrReviewOptions({ path: { work_item_id: auditId } }).queryKey,
      });
    },
  });
  const reviewed = card.reviewed_at != null;
  return (
    <section data-card={card.source_ref} className="rounded-[12px] bg-card e1">
      <header className="flex h-[40px] items-center gap-[8px] px-[14px] text-[13.5px] font-medium">
        <StatusDisc state={reviewed ? "done" : "todo"} size={15} />
        {card.title}
        {/^AUD-20\b/.test(card.source_ref) && (
          <a
            href={hrefOf(to.AUD20({ auditId }))}
            className="ml-auto text-[12px] font-normal text-ink-2 hover:underline"
          >
            {COPY.openStatements}
          </a>
        )}
      </header>
      <div className="px-[14px] pb-[12px]">
        {card.rows.map((row) => (
          <div
            key={row.label}
            className="flex min-h-[30px] items-center justify-between gap-[12px] text-[12.5px]"
          >
            <span className="text-ink-2">{row.label}</span>
            <span className="text-right">{row.value}</span>
          </div>
        ))}
      </div>
      <footer className="flex items-center justify-between px-[14px] pb-[10px]">
        <button
          type="button"
          data-cite={card.link_target}
          onClick={() => onCited?.(card.link_target)}
        >
          <Pill size="chip" variant="neutral">
            {card.link_target}
          </Pill>
        </button>
        {canMark && !reviewed && (
          <Button
            variant="secondary"
            size="xs"
            onClick={() => {
              mark.mutate({
                path: { work_item_id: auditId, card_id: card.id },
                body: { reviewed: true },
                headers: { "Idempotency-Key": crypto.randomUUID() },
              });
            }}
          >
            {COPY.markReviewed}
          </Button>
        )}
      </footer>
    </section>
  );
}

function Note({ note, isEqr }: { note: EqrNoteRowOut; isEqr: boolean }): JSX.Element {
  return (
    <article
      data-note={note.ref}
      data-status={note.status}
      className="rounded-[10px] bg-card px-[12px] py-[10px] e1"
    >
      <div className="flex items-center justify-between text-[12.5px] font-medium">
        {note.ref}
        <Pill size="micro" variant={note.status === "open" ? "amber" : "neutral"}>
          {COPY.note[note.status]}
        </Pill>
      </div>
      {note.assignee_name != null && (
        <p className="text-[11.5px] text-ink-3">{COPY.note.assigned(note.assignee_name)}</p>
      )}
      {isEqr && note.status === "responded" && (
        <div className="mt-[6px] flex gap-[6px]">
          <Button size="xs">{COPY.note.clear}</Button>
          <Button size="xs" variant="secondary">
            {COPY.note.reopen}
          </Button>
        </div>
      )}
    </article>
  );
}

function ConcurSheet({
  view,
  auditId,
  onClose,
}: {
  view: EqrReviewOut;
  auditId: string;
  onClose: () => void;
}): JSX.Element {
  const client = useQueryClient();
  const [attested, setAttested] = useState(false);
  const concur = useMutation({
    ...eqrConcurMutation(),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: eqrReviewOptions({ path: { work_item_id: auditId } }).queryKey,
      });
      onClose();
    },
  });
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.sheet.title}
      size="sm"
    >
      <div data-sheet="concur" className="flex flex-col gap-[8px] text-[12.5px]">
        <ul className="list-disc pl-[16px]">
          {view.digest_cards.map((c) => (
            <li key={c.id}>{c.title}</li>
          ))}
        </ul>
        <p>{COPY.sheet.date}</p>
        <label className="flex items-center gap-[6px]">
          <input
            type="checkbox"
            checked={attested}
            onChange={(e) => {
              setAttested(e.target.checked);
            }}
          />
          {COPY.sheet.attest}
        </label>
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.sheet.cancel}
          </Button>
          <Button
            disabled={!attested || concur.isPending}
            onClick={() => {
              concur.mutate({
                path: { work_item_id: auditId },
                body: {
                  not_involved: true,
                  concurrence_date: "2026-10-05",
                  seen_version: view.version,
                },
                headers: { "Idempotency-Key": crypto.randomUUID() },
              });
            }}
          >
            {COPY.sheet.concur}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function ConcurrenceCard({
  view,
  onConcur,
}: {
  view: EqrReviewOut;
  onConcur: () => void;
}): JSX.Element {
  const fmt = useFormat();
  const open = view.checklist_total - view.checklist_done;
  const notes = view.notes.filter((n) => n.status !== "cleared").length;
  const can = view.allowed_actions.includes("eqr.concur");
  if (view.concurrence != null) {
    return (
      <section
        data-concurrence="done"
        className="m-[10px] rounded-[12px] bg-green-tint p-[12px] text-[12.5px] text-green-ink e2"
      >
        <p>
          {COPY.concurrence.done(
            fmt.dateTime(view.concurrence.concurred_at),
            view.concurrence.concurred_by_name,
          )}
        </p>
        <p className="font-medium">{COPY.concurrence.met}</p>
      </section>
    );
  }
  return (
    <section
      data-concurrence={can ? "ready" : "blocked"}
      className="m-[10px] rounded-[12px] bg-card p-[12px] e2"
    >
      <p className="text-[13.5px] font-medium">{COPY.concurrence.title}</p>
      <p className="text-[12.5px] text-ink-2">
        {can ? COPY.concurrence.ready : COPY.concurrence.blocked(open, notes)}
      </p>
      {!view.viewer_is_eqr && (
        <p data-not-eqr className="text-[12.5px] text-ink-2">
          {COPY.notEqr}
        </p>
      )}
      {view.viewer_is_eqr && (
        <Button className="mt-[8px] w-full" disabled={!can} onClick={onConcur}>
          {COPY.concurrence.action}
        </Button>
      )}
    </section>
  );
}

export function EqrWorkspacePage({
  auditId,
  dock: initialDock = "notes",
  concurring = false,
  onBack,
  onSourceDocs,
  onCited,
}: EqrWorkspaceProps): JSX.Element {
  const cockpit = useAuditCockpit(auditId);
  const found = useQuery({
    ...eqrReviewOptions({ path: { work_item_id: auditId } }),
    retry: false,
  });
  const [dock, setDock] = useState<Dock>(initialDock);
  const [sheet, setSheet] = useState(concurring);
  const view = found.data;
  let state: ViewState = { kind: "ready" };
  if (found.isError) {
    state = isNotFound(found.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void found.refetch() };
  } else if (view === undefined) state = { kind: "loading" };
  const canMark = view?.allowed_actions.includes("eqr.mark_reviewed") === true;
  const source = onSourceDocs === undefined ? {} : { onClick: onSourceDocs };
  return (
    <div data-screen="AUD-18" className="flex min-h-0 flex-1 flex-col">
      <ViewStateBody state={state} empty={{ title: COPY.canvas }}>
        {cockpit.data !== undefined && (
          <AuditBar cockpit={cockpit.data} {...(onBack === undefined ? {} : { onBack })} />
        )}
        {view !== undefined && (
          <div className="grid min-h-0 flex-1 grid-cols-[330px_696px_330px] gap-[10px] p-[12px]">
            <aside data-pane="rail" className={PANE}>
              <div className={cn(HEADER, "justify-center")}>{COPY.rail}</div>
              <div
                data-overview
                className="mx-[10px] rounded-[12px] bg-shell p-[12px] text-[12.5px]"
              >
                <p className="text-[11.5px] text-ink-3">{COPY.overview.subtitle(view.eqr_name)}</p>
                <Pill size="chip" variant="neutral">
                  {COPY.overview.complete(view.checklist_done, view.checklist_total)}
                </Pill>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto pt-[8px]">
                {view.checklist.map((item) => (
                  <Row key={item.item_key} item={item} />
                ))}
              </div>
            </aside>
            <main data-pane="canvas" className={PANE}>
              <div className={HEADER}>
                <span>
                  {COPY.canvas}{" "}
                  <span className="text-[11.5px] font-normal text-ink-3">
                    {COPY.built(view.digest_cards.length)}
                  </span>
                </span>
                <Button variant="secondary" size="xs" {...source}>
                  {COPY.sourceDocs}
                </Button>
              </div>
              <div className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto bg-shell p-[10px]">
                {view.digest_cards.map((card) => (
                  <Card
                    key={card.id}
                    card={card}
                    canMark={canMark}
                    auditId={auditId}
                    onCited={onCited}
                  />
                ))}
              </div>
            </main>
            <aside data-pane="dock" className={PANE}>
              <div className={cn(HEADER, "justify-center")}>
                <Segmented
                  label={COPY.dock.notes}
                  size="small"
                  active={COPY.dock[dock]}
                  options={[COPY.dock.notes, COPY.dock.agent]}
                  onChange={(label) => {
                    setDock(label === COPY.dock.agent ? "agent" : "notes");
                  }}
                />
              </div>
              <div className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-y-auto p-[10px]">
                {dock === "notes" ? (
                  view.notes.map((note) => (
                    <Note key={note.id} note={note} isEqr={view.viewer_is_eqr} />
                  ))
                ) : (
                  <div data-agent className="flex flex-col gap-[6px] text-[12.5px]">
                    <p className="rounded-[10px] p-[8px] e1">✓ {COPY.agent.tool}</p>
                    <p className="text-ink-2">{COPY.agent.narration}</p>
                  </div>
                )}
              </div>
              <ConcurrenceCard
                view={view}
                onConcur={() => {
                  setSheet(true);
                }}
              />
            </aside>
          </div>
        )}
        {view === undefined && <Skeleton className="m-[12px] h-[240px]" />}
      </ViewStateBody>
      {sheet && view !== undefined && (
        <ConcurSheet
          view={view}
          auditId={auditId}
          onClose={() => {
            setSheet(false);
          }}
        />
      )}
    </div>
  );
}
