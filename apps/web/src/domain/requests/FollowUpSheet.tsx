// The follow-up sheet (P-06-T16; BND-01 "Send reminder(s)…", BND-02 d "Send reminder…"; DEC-221).
// O3 500 over the screen, drawn as BND-04 c draws the same sheet: one card per client contact
// with the drafted email, its open requests (each once, "overdue" in red ink), the C-31 marker
// and "Edit"; the footer says nothing is sent until the person clicks Send. The drafts are the
// Request Chaser's, composed from the firm's published Reminder template (never model text,
// DEC-79); Send is the person's (DEC-74) and has ten seconds to Undo (ADR-161).

import { Button, Icon, SheetModal, toast } from "@abacus/ui";
import { type JSX, useEffect, useState } from "react";
import { type FollowUp, type FollowUpSelection, useFollowUps } from "./followUps";

/** Verbatim from BND-04 c (spec.md STATES c, d); the sheet is the same O3 the BND screens open. */
export const FOLLOW_UP_COPY = {
  title: (n: number) => `Send follow-ups · ${String(n)}`,
  to: (name: string) => `To ${name}`,
  items: (n: number, overdue: number) =>
    overdue > 0 ? `${String(n)} items, ${String(overdue)} overdue` : `${String(n)} items`,
  overdue: "overdue",
  more: (n: number) => `+ ${String(n)} more open items listed once in the email`,
  marker: "Drafted by Accrued Agent (Request Chaser) · not sent · Reminder template (POR-20)",
  edit: "Edit",
  editLabel: (name: string) => `Follow-up to ${name}`,
  footer: "Nothing is sent until you click Send.",
  cancel: "Cancel",
  send: (n: number) => (n === 1 ? "Send 1 follow-up" : `Send ${String(n)} follow-ups`),
  sent: (n: number, person: string) =>
    n === 1 ? `1 follow-up sent by ${person}` : `${String(n)} follow-ups sent by ${person}`,
  // Not drawn by the handoff (DEC-221): the toast rules' wording.
  nothing: "Every open request already has a follow-up waiting",
  failed: "Couldn’t draft the follow-ups",
  sendFailed: "Couldn’t send the follow-ups",
} as const;

const SHOWN = 5;

export interface FollowUpSheetProps {
  /** What to draft for; null keeps the sheet closed. */
  selection: FollowUpSelection | null;
  onClose: () => void;
  /** The signed-in person, named in the sent toast ("3 follow-ups sent by Grace Holloway"). */
  person: string;
}

export function FollowUpSheet({ selection, onClose, person }: FollowUpSheetProps): JSX.Element {
  const followUps = useFollowUps();
  const [drafts, setDrafts] = useState<FollowUp[] | null>(null);
  const key = selection === null ? null : JSON.stringify(selection);

  useEffect(() => {
    if (selection === null) {
      setDrafts(null);
      return;
    }
    let live = true;
    followUps.draft(selection).then(
      (made) => {
        if (!live) return;
        if (made.length === 0) {
          toast.show({ kind: "info", text: FOLLOW_UP_COPY.nothing });
          onClose();
          return;
        }
        setDrafts(made);
      },
      () => {
        if (!live) return;
        toast.show({ kind: "error", text: FOLLOW_UP_COPY.failed });
        onClose();
      },
    );
    return () => {
      live = false;
    };
    // The selection's content, not its identity, asks for a new draft.
  }, [key]);

  const replace = (next: FollowUp): void => {
    setDrafts((all) => (all ?? []).map((d) => (d.id === next.id ? next : d)));
  };

  const send = async (): Promise<void> => {
    if (drafts === null) return;
    const ids = drafts.map((d) => d.id);
    try {
      const sent = await followUps.send(ids);
      onClose();
      toast.undoable({
        text: FOLLOW_UP_COPY.sent(sent.length, person),
        undo: () => {
          for (const id of ids) void followUps.undo(id);
        },
      });
    } catch {
      toast.show({ kind: "error", text: FOLLOW_UP_COPY.sendFailed });
    }
  };

  const n = drafts?.length ?? 0;
  return (
    <SheetModal
      open={selection !== null && drafts !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={FOLLOW_UP_COPY.title(n)}
      footer={
        <div className="flex w-full items-center gap-[8px]">
          <span className="text-meta text-ink-3">{FOLLOW_UP_COPY.footer}</span>
          <span className="ml-auto flex items-center gap-[8px]">
            <Button variant="ghost" size="md" onClick={onClose}>
              {FOLLOW_UP_COPY.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={n === 0 || followUps.sending}
              onClick={() => void send()}
            >
              {FOLLOW_UP_COPY.send(n)}
            </Button>
          </span>
        </div>
      }
    >
      <div className="flex flex-col gap-[10px]">
        {(drafts ?? []).map((draft) => (
          <FollowUpCard
            key={draft.id}
            draft={draft}
            onEdit={async (body) => {
              replace(await followUps.edit(draft.id, body));
            }}
          />
        ))}
      </div>
    </SheetModal>
  );
}

function FollowUpCard({
  draft,
  onEdit,
}: {
  draft: FollowUp;
  onEdit: (body: string) => Promise<void>;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft.body);
  const overdue = draft.items.filter((i) => i.overdue).length;
  const hidden = Math.max(0, draft.items.length - SHOWN);
  const save = async (): Promise<void> => {
    const next = text.trim();
    if (next !== "" && next !== draft.body) {
      try {
        await onEdit(next);
      } catch {
        toast.show({ kind: "error", text: FOLLOW_UP_COPY.failed });
      }
    }
    setEditing(false);
  };
  return (
    <article
      data-follow-up={draft.id}
      className="flex flex-col gap-[10px] rounded-pane bg-card p-[14px] shadow-e1"
    >
      <header className="flex items-start gap-[8px]">
        <div className="min-w-0 flex-1">
          <h3 className="text-dense font-medium text-ink">
            {FOLLOW_UP_COPY.to(draft.recipient_name)}
          </h3>
          <p className="text-meta text-ink-3">
            {FOLLOW_UP_COPY.items(draft.items.length, overdue)}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          aria-pressed={editing}
          onClick={() => {
            if (editing) void save();
            else {
              setText(draft.body);
              setEditing(true);
            }
          }}
        >
          {FOLLOW_UP_COPY.edit}
        </Button>
      </header>
      {editing ? (
        <textarea
          aria-label={FOLLOW_UP_COPY.editLabel(draft.recipient_name)}
          value={text}
          rows={8}
          onChange={(event) => {
            setText(event.target.value);
          }}
          onBlur={() => void save()}
          className="w-full resize-none rounded-nested bg-card p-[10px] text-body leading-[1.5] text-ink shadow-e1 outline-offset-[-2px]"
        />
      ) : (
        <p className="whitespace-pre-line text-para text-ink-2 [overflow-wrap:anywhere]">
          {draft.body}
        </p>
      )}
      <ul className="flex flex-col gap-[4px] rounded-nested bg-band-hd px-[12px] py-[8px]">
        {draft.items.slice(0, SHOWN).map((item) => (
          <li key={item.request_item_id} className="flex items-baseline gap-[8px] text-dense">
            <span className="min-w-0 flex-1 truncate text-ink">{item.title}</span>
            {item.overdue && (
              <span className="text-meta text-red-ink">{FOLLOW_UP_COPY.overdue}</span>
            )}
          </li>
        ))}
        {hidden > 0 && <li className="text-meta text-ink-3">{FOLLOW_UP_COPY.more(hidden)}</li>}
      </ul>
      <p className="flex items-start gap-[6px] text-meta text-ink-3">
        <Icon name="atom" size={13} aria-hidden />
        <span>{FOLLOW_UP_COPY.marker}</span>
      </p>
    </article>
  );
}
