import type {
  ReviewNoteDetailOut,
  ReviewNoteItemOut,
  SignOffMatrixCellOut,
  SignOffMatrixRowOut,
} from "@abacus/api-client";
import {
  epInvolvementOptions,
  reviewNoteClearMutation,
  reviewNoteListOptions,
  reviewNoteOptions,
  reviewNoteReopenMutation,
  reviewNoteRespondMutation,
  signOffMatrixOptions,
} from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  type IssueGroup,
  IssueQueue,
  Pill,
  QueueDetailLayout,
  type ReviewNoteMessage,
  ReviewNoteThread,
  Segmented,
  Skeleton,
  Timeline,
  cn,
  date,
} from "@abacus/ui";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { COPY } from "./copy";

// AUD-17 · Review notes & sign-off matrix (A-06-T24; the handoff spec): T9 close-review under the
// Evaluation tabs. The queue bands notes (Open · Responded · Cleared collapsed); the thread shows the
// messages with the anchor chip, and Clear and Reopen as the server allows them. The matrix is the
// server's rows and footer (A-06-T23): a chip opens SHL-12 and never signs, an empty L4 opens the
// sign-off, a stale cell's popover asks for a re-review. The legend says a review note blocks sign-off
// and a comment never does; it isn't a filter. Totals come from the server (no counting in the
// browser beyond the bands of the rows it was given).

type Band = keyof typeof COPY.bands;
const BANDS: readonly Band[] = ["open", "responded", "cleared"];
const SECTIONS = ["planning", "fieldwork", "completion", "reporting"] as const;
type MatrixView = keyof typeof COPY.matrix.segments;

function bandOf(status: ReviewNoteItemOut["status"]): Band {
  if (status === "open") return "open";
  if (status === "responded") return "responded";
  return "cleared";
}

function SignOffCell({
  cell,
  row,
  onSignOff,
}: {
  cell: SignOffMatrixCellOut;
  row: SignOffMatrixRowOut;
  onSignOff: (type: string, id: string, level: number) => void;
}): JSX.Element {
  const now = useNow();
  const [open, setOpen] = useState(false);
  if (cell.state === "not_required") {
    return <span className="text-ink-4">{COPY.matrix.notRequired}</span>;
  }
  if (cell.state === "pending") {
    return (
      <button
        type="button"
        data-cell={`${row.code}:L${String(cell.level)}`}
        aria-label={`${COPY.matrix.levels[cell.level - 1] ?? ""} ${row.title}`}
        className="inline-block size-[15px] rounded-full ring-[1px] ring-ink-3"
        onClick={() => {
          onSignOff(row.target_type, row.target_id, cell.level);
        }}
      />
    );
  }
  if (cell.state === "stale") {
    return (
      <span className="relative inline-block">
        <button
          type="button"
          data-cell={`${row.code}:L${String(cell.level)}`}
          data-state="stale"
          aria-expanded={open}
          onClick={() => {
            setOpen((v) => !v);
          }}
        >
          <Pill variant="amber" size="chip">
            <span className="line-through">✓ {cell.initials}</span>
          </Pill>
        </button>
        {open && (
          <div
            role="dialog"
            aria-label={COPY.matrix.staleTitle}
            data-aud17="stale-popover"
            className="absolute right-0 z-10 mt-[4px] w-[220px] rounded-[8px] bg-card p-[10px] text-left text-[12px] shadow-e2"
          >
            <p className="font-medium">{COPY.matrix.staleTitle}</p>
            <p className="text-ink-2">
              {cell.signed_at === null ? "" : date(cell.signed_at, { now, withYear: true })} ·{" "}
              {COPY.matrix.staleBody}
            </p>
            <Button
              size="xs"
              variant="secondary"
              className="mt-[6px]"
              onClick={() => {
                onSignOff(row.target_type, row.target_id, cell.level);
              }}
            >
              {COPY.matrix.requestReReview}
            </Button>
          </div>
        )}
      </span>
    );
  }
  return (
    <button
      type="button"
      data-cell={`${row.code}:L${String(cell.level)}`}
      data-state="signed"
      className="rounded-[4px] bg-green px-[5px] text-[10.5px] leading-[18px] font-medium text-on-dark"
      onClick={() => {
        onSignOff(row.target_type, row.target_id, cell.level);
      }}
    >
      ✓ {cell.initials}
    </button>
  );
}

function MatrixPane({
  workItemId,
  onSignOff,
}: {
  workItemId: string;
  onSignOff: (type: string, id: string, level: number) => void;
}): JSX.Element {
  const now = useNow();
  const [view, setView] = useState<MatrixView>("matrix");
  const matrix = useQuery(signOffMatrixOptions({ path: { work_item_id: workItemId } }));
  const involvement = useQuery({
    ...epInvolvementOptions({ path: { work_item_id: workItemId } }),
    enabled: view === "involvement",
  });
  const rows = matrix.data?.rows ?? [];
  const footer = matrix.data?.footer;
  return (
    <section
      aria-label={COPY.matrix.title}
      data-aud17="matrix-pane"
      className="flex min-h-0 flex-1 flex-col"
    >
      <h3 className="flex h-[46px] items-center justify-center text-pane-title font-medium hairline-b">
        {COPY.matrix.title}
      </h3>
      <div className="flex h-[54px] items-center justify-center hairline-b">
        <Segmented
          label={COPY.matrix.title}
          active={COPY.matrix.segments[view]}
          onChange={(label) => {
            setView(label === COPY.matrix.segments.matrix ? "matrix" : "involvement");
          }}
          options={[COPY.matrix.segments.matrix, COPY.matrix.segments.involvement]}
        />
      </div>
      {view === "involvement" ? (
        <div data-aud17="involvement" className="min-h-0 flex-1 overflow-y-auto p-[16px]">
          <Timeline
            label={COPY.matrix.segments.involvement}
            events={(involvement.data?.items ?? []).map((e, i) => ({
              id: `${e.kind}-${String(i)}`,
              date: date(e.at, { now }),
              state: e.kind === "sign_off" ? ("done" as const) : ("half" as const),
              title: `${e.subject} ${e.outcome}`,
              detail: e.by_name,
            }))}
          />
        </div>
      ) : (
        <>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-[12.5px]" data-aud17="matrix">
              <thead>
                <tr className="h-[30px] bg-band-hd text-th font-medium text-ink-3">
                  <th className="w-[236px] px-[12px] text-left font-medium">
                    {COPY.matrix.workpaper}
                  </th>
                  {COPY.matrix.levels.map((l) => (
                    <th key={l} className="w-[64px] text-center font-medium">
                      {l}
                    </th>
                  ))}
                </tr>
              </thead>
              {SECTIONS.map((section) => {
                const group = rows.filter((r) => r.section === section);
                if (group.length === 0) return null;
                return (
                  <tbody key={section}>
                    <tr className="h-[24px] text-[11px] font-medium text-ink-3">
                      <td colSpan={6} className="px-[12px]">
                        {COPY.matrix.groups[section]}
                      </td>
                    </tr>
                    {group.map((row) => (
                      <tr key={row.target_id} data-row={row.code} className="h-[32px] hairline-t">
                        <td className="px-[12px]">{row.title}</td>
                        {row.cells.map((cell) => (
                          <td key={cell.level} className="text-center">
                            <SignOffCell cell={cell} row={row} onSignOff={onSignOff} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                );
              })}
            </table>
          </div>
          {footer !== undefined && (
            <div
              data-aud17="footer"
              className="flex min-h-[30px] items-center px-[12px] text-[11px] text-ink-3 hairline-t"
            >
              {COPY.matrix.footer({
                workpapers: rows.length,
                prepared: footer.prepared,
                reviewed: footer.reviewed,
                partner: `${String(footer.partner_signed)} of ${String(footer.partner_required)}`,
                eqr: `${String(footer.eqr_signed)} of ${String(footer.eqr_required)}`,
                changed: footer.changed_after_sign_off,
              })}
            </div>
          )}
          <p data-aud17="legend" className="px-[12px] pb-[8px] text-[11px] text-ink-3">
            {COPY.matrix.legend}
          </p>
        </>
      )}
    </section>
  );
}

function messagesOf(detail: ReviewNoteDetailOut, now: Date): ReviewNoteMessage[] {
  return detail.events
    .filter((e) => e.body != null && e.body !== "")
    .map((e, i) => ({
      id: `${e.at}:${String(i)}`,
      who: e.actor_name,
      at: date(e.at, { now }),
      body: e.body,
    }));
}

function Thread({ noteId, onCleared }: { noteId: string; onCleared: () => void }): JSX.Element {
  const now = useNow();
  const client = useQueryClient();
  const found = useQuery(reviewNoteOptions({ path: { note_id: noteId } }));
  const refresh = (): void => {
    void client.invalidateQueries();
  };
  const clear = useMutation({
    ...reviewNoteClearMutation(),
    onSuccess: () => {
      refresh();
      onCleared();
    },
  });
  const respond = useMutation({ ...reviewNoteRespondMutation(), onSuccess: refresh });
  // Reopen needs why (SPEC-313 AC-3): the button opens the composer, and Send reopens with it.
  const [reopening, setReopening] = useState(false);
  const reopen = useMutation({
    ...reviewNoteReopenMutation(),
    onSuccess: () => {
      setReopening(false);
      refresh();
    },
  });
  if (found.data === undefined) return <Skeleton className="m-[12px] h-[160px]" />;
  const { note, body } = found.data;
  const can = (action: string): boolean => note.allowed_actions.includes(action);
  const canReopen = can("review_note.reopen");
  return (
    <div data-aud17="thread" className="flex min-h-0 flex-1 flex-col">
      <h3 className="bg-shell px-[14px] py-[12px] text-[15px] leading-[1.3] font-medium">
        {body}
      </h3>
      {[
        [COPY.kv.anchor, note.anchor?.ref ?? ""],
        [COPY.kv.author, note.raised_by_initials],
        [COPY.kv.status, COPY.status[note.status]],
        [COPY.kv.opened, date(note.raised_at, { now, withYear: true })],
      ].map(([k, v]) => (
        <div key={k} className="flex h-[35px] items-center px-[14px] text-[12.5px] hairline-t">
          <span className="w-[110px] text-ink-2">{k}</span>
          <span>{v}</span>
        </div>
      ))}
      {found.data.paper_changed_after_signoff === true && (
        <p
          data-aud17="stale-notice"
          role="status"
          className="mx-[14px] mt-[10px] rounded-[6px] bg-amber-tint px-[10px] py-[8px] text-[12.5px] text-amber-ink"
        >
          {COPY.staleNotice}
        </p>
      )}
      <ReviewNoteThread
        messages={messagesOf(found.data, now)}
        replyLabel={COPY.reply}
        sendLabel={COPY.send}
        busy={respond.isPending || reopen.isPending}
        {...(canReopen && reopening
          ? {
              onReply: (text: string) => {
                reopen.mutate({ path: { note_id: noteId }, body: { body: text } });
              },
            }
          : can("review_note.respond")
            ? {
                onReply: (text: string) => {
                  respond.mutate({ path: { note_id: noteId }, body: { body: text } });
                },
              }
            : {})}
      />
      <div className="flex flex-col gap-[6px] p-[10px] hairline-t">
        <Button
          variant="primary"
          disabled={!can("review_note.clear") || clear.isPending}
          onClick={() => {
            clear.mutate({ path: { note_id: noteId }, body: {} });
          }}
        >
          {COPY.clear}
        </Button>
        <Button
          variant="secondary"
          data-aud17="reopen"
          disabled={!canReopen || reopening || reopen.isPending}
          onClick={() => {
            setReopening(true);
          }}
        >
          {COPY.reopen}
        </Button>
      </div>
    </div>
  );
}

export function ReviewNotesPane({
  engagementId,
  workItemId,
  onSignOff,
}: {
  engagementId: string;
  workItemId: string;
  /** SHL-12: a chip opens the modal and never signs. */
  onSignOff: (type: string, id: string, level: number) => void;
}): JSX.Element {
  const list = useQuery(reviewNoteListOptions({ query: { engagement_id: engagementId } }));
  const rows = list.data?.items ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  const [showCleared, setShowCleared] = useState(false);
  const details = useQueries({
    queries: rows.map((r) => reviewNoteOptions({ path: { note_id: r.id } })),
  });
  const titleOf = (id: string): string =>
    details.find((d) => d.data?.note.id === id)?.data?.body ?? "";
  const groups: IssueGroup[] = BANDS.flatMap((band) => {
    const items = rows.filter((r) => bandOf(r.status) === band);
    if (items.length === 0) return [];
    return [
      {
        id: band,
        label: COPY.bands[band],
        count: String(items.length),
        defaultOpen: band !== "cleared" || showCleared,
        items: items.map((r) => ({
          id: r.id,
          title: titleOf(r.id),
          sub: [COPY.status[r.status], r.raised_by_initials, r.anchor?.ref ?? ""]
            .filter((s) => s !== "")
            .join(" · "),
          ...(band === "open" ? { flag: "red" as const } : {}),
        })),
      },
    ];
  });
  const selected = picked ?? rows.find((r) => bandOf(r.status) !== "cleared")?.id ?? null;
  const queueBody =
    list.data !== undefined && rows.length === 0 ? (
      <EmptyState icon="inbox" title={COPY.empty.title}>
        {COPY.empty.body}
      </EmptyState>
    ) : (
      <IssueQueue
        variant="severity"
        label={COPY.queue}
        groups={groups}
        {...(selected === null ? {} : { selected })}
        onSelect={(item) => {
          setPicked(item.id);
        }}
      />
    );
  return (
    <div data-screen="AUD-17" className={cn("flex min-h-0 flex-1")}>
      <QueueDetailLayout
        preset="close-review"
        bare
        toolbar={{ nav: [], active: "Audits", firm: "" }}
        record={null}
        queue={{
          title: COPY.queue,
          right: (
            <button
              type="button"
              aria-pressed={showCleared}
              onClick={() => {
                setShowCleared((v) => !v);
              }}
              className="text-body text-ink-3 hover:text-ink"
            >
              {COPY.showCleared}
            </button>
          ),
          body: queueBody,
        }}
        detail={{
          body:
            selected === null ? null : (
              <Thread
                key={selected}
                noteId={selected}
                onCleared={() => {
                  setPicked(null);
                }}
              />
            ),
        }}
        evidence={[<MatrixPane key="matrix" workItemId={workItemId} onSignOff={onSignOff} />]}
      />
    </div>
  );
}
