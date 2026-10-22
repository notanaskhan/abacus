import type { NoteOut } from "@abacus/api-client";
import {
  clearNoteMutation,
  notesQueryKey,
  raiseNoteMutation,
  respondNoteMutation,
} from "@abacus/api-client/query";
import { Badge, Button, DateText, Drawer, Fieldset, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-041 (TASK-103): review notes in a drawer: a reviewer raises one on a row or the
// workpaper, the preparer responds, the raiser clears it. Notes block the reviewer's sign-off;
// comments never do.

const STATE = {
  open: { label: "Open", tone: "danger" },
  responded: { label: "Responded", tone: "warning" },
  cleared: { label: "Cleared", tone: "success" },
} as const;

const SAID: Record<string, string> = {
  not_note_raiser: "Only the person who raised a note clears it.",
  note_cleared: "This note is already cleared.",
  note_invalid: "Write the note first.",
};

function said(error: unknown): string {
  return SAID[errorMessage(error)] ?? "That didn't work. Try again.";
}

const RAISERS = new Set(["engagement_partner", "manager", "senior", "reviewer"]);
const RESPONDERS = new Set(["engagement_partner", "manager", "senior", "staff", "reviewer"]);

/** A row's (or the workpaper's) open notes, as a small count that opens the drawer. */
export function NoteCount({
  notes,
  onOpen,
  canRaise,
}: {
  notes: NoteOut[];
  onOpen: () => void;
  canRaise: boolean;
}): JSX.Element | null {
  const open = notes.filter((n) => n.state !== "cleared").length;
  if (open === 0 && !canRaise && notes.length === 0) return null;
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={open > 0 ? `${String(open)} open review notes` : "Review notes"}
      className="rounded-[5px] text-left hover:opacity-80"
    >
      {open > 0 ? (
        <Badge tone="danger">{`${String(open)} ${open === 1 ? "note" : "notes"}`}</Badge>
      ) : (
        <span className="text-[11.5px] text-ink-3 underline">
          {notes.length > 0 ? "Notes" : "Add note"}
        </span>
      )}
    </button>
  );
}

export function NotesDrawer({
  open,
  onOpenChange,
  engagementId,
  procedureId,
  itemId,
  title,
  notes,
  role,
  me,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  engagementId: string;
  procedureId: string;
  /** null: the workpaper. */
  itemId: string | null;
  title: string;
  notes: NoteOut[];
  role: string | undefined;
  me: string | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { engagement_id: engagementId, procedure_id: procedureId };
  const [draft, setDraft] = useState("");
  const done = (data: NoteOut[]): void => {
    queryClient.setQueryData(notesQueryKey({ path }), data);
  };
  const raise = useMutation({
    ...raiseNoteMutation(),
    onSuccess: (data) => {
      done(data);
      setDraft("");
      toast.show("Note raised");
    },
  });
  const shown = notes.filter((n) => (n.item_id ?? null) === itemId);
  const canRaise = RAISERS.has(role ?? "");
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description="Review notes block the reviewer's sign-off until the person who raised them clears them."
    >
      {shown.length === 0 && <p className="mb-3 text-[12.5px] text-ink-2">No review notes yet.</p>}
      {shown.map((n) => (
        <NoteCard
          key={n.id}
          note={n}
          path={path}
          onDone={done}
          canRespond={RESPONDERS.has(role ?? "")}
          isRaiser={n.raised_by === me}
        />
      ))}
      {canRaise && (
        <Fieldset title="Raise a note">
          <textarea
            aria-label="New review note"
            value={draft}
            maxLength={2000}
            onChange={(e) => {
              setDraft(e.target.value);
            }}
            placeholder="What needs to change before you can sign this off"
            className="min-h-[72px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
          />
          <div className="mt-2 flex items-center justify-end gap-2">
            {raise.isError && <span className="text-meta text-danger">{said(raise.error)}</span>}
            <Button
              size="sm"
              disabled={draft.trim() === "" || raise.isPending}
              onClick={() => {
                raise.mutate({ path, body: { item_id: itemId, body: draft } });
              }}
            >
              Raise note
            </Button>
          </div>
        </Fieldset>
      )}
    </Drawer>
  );
}

function NoteCard({
  note,
  path,
  onDone,
  canRespond,
  isRaiser,
}: {
  note: NoteOut;
  path: { engagement_id: string; procedure_id: string };
  onDone: (data: NoteOut[]) => void;
  canRespond: boolean;
  isRaiser: boolean;
}): JSX.Element {
  const [reply, setReply] = useState("");
  const respond = useMutation({
    ...respondNoteMutation(),
    onSuccess: (data) => {
      onDone(data);
      setReply("");
    },
  });
  const clear = useMutation({
    ...clearNoteMutation(),
    onSuccess: (data) => {
      onDone(data);
      toast.show("Note cleared");
    },
  });
  const state = STATE[note.state];
  const closed = note.state === "cleared";
  return (
    <Fieldset {...(closed ? { className: "opacity-70" } : {})}>
      <div className="mb-2 flex items-center gap-2">
        <StatusPill tone={state.tone}>{state.label}</StatusPill>
        <span className="text-[11.5px] text-ink-3">
          Raised by {note.raised_by_name || "a reviewer"} · <DateText value={note.raised_at} />
        </span>
      </div>
      <ol className="flex flex-col gap-2" aria-label="Thread">
        {note.thread.map((t, n) => (
          <li key={n} className="text-[13px]">
            {t.kind === "cleared" ? (
              <span className="text-[12px] text-ink-3">{`Cleared by ${t.name}`}</span>
            ) : (
              <>
                <span className="text-[11.5px] text-ink-3">
                  {t.kind === "raised"
                    ? t.name
                    : `${t.name} · ${t.kind === "reopened" ? "replied" : "responded"}`}
                </span>
                <p className="leading-[1.5] whitespace-pre-line">{t.body}</p>
              </>
            )}
          </li>
        ))}
      </ol>
      {!closed && (canRespond || isRaiser) && (
        <div className="mt-2.5 flex flex-col gap-2">
          <textarea
            aria-label="Reply to this note"
            value={reply}
            maxLength={2000}
            onChange={(e) => {
              setReply(e.target.value);
            }}
            placeholder={isRaiser ? "Reply (reopens the note)" : "Respond"}
            className="min-h-[52px] w-full rounded-tile border-0 bg-nested p-2 text-[13px] inset-shadow-hair focus:bg-card"
          />
          <div className="flex items-center justify-end gap-2">
            {(respond.isError || clear.isError) && (
              <span className="text-meta text-danger">{said(respond.error ?? clear.error)}</span>
            )}
            {isRaiser && (
              <Button
                size="sm"
                variant="success"
                disabled={clear.isPending}
                onClick={() => {
                  clear.mutate({ path: { ...path, note_id: note.id } });
                }}
              >
                Clear note
              </Button>
            )}
            <Button
              size="sm"
              variant="secondary"
              disabled={reply.trim() === "" || respond.isPending}
              onClick={() => {
                respond.mutate({ path: { ...path, note_id: note.id }, body: { body: reply } });
              }}
            >
              {isRaiser ? "Reply" : "Respond"}
            </Button>
          </div>
        </div>
      )}
    </Fieldset>
  );
}
