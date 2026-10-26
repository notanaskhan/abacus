// ScopedRequestRoom (R-01 §5.2, L3; docs/screens/POR-14.md): a room of requests delegated to one
// outside person, and nothing else. POR-14 draws it for third parties; A-09 reuses it for POR-23.
//
//   intro     the engagement, what the firm asked the organisation for, "n of N uploaded" with
//             its bar, and the "Drop files here" pill
//   bands     the request's category as a folder band, "n of N"; each row its sub-line and an
//             18 disc (olive done, ring owed); a row opens to the firm's guidance, its files
//             (Withdraw on the person's own unaccepted upload), the upload slot and the thread
//   picker    files dropped on the pill with more than one open request: "Which request is
//             this for?", pre-selected by the server's code-only scoring of the names
//
// The firm's words (titles, guidance, notes) are shown as written; the person never sees another
// party, a firm status, the agent or the product's name (INV-4, DEC-01). Uploading, withdrawing and
// commenting are the person's own acts on the request delegated to them.

import type { PortalFileOut, PortalRoomOut, PortalRoomRowOut } from "@abacus/api-client";
import {
  Button,
  ConfirmDialog,
  Dialog,
  Icon,
  RadioGroup,
  StatusDisc,
  bytes,
  cn,
} from "@abacus/ui";
import { type DragEvent, type JSX, useRef, useState } from "react";
import { DOCUMENT_WORDS, ROOM_WORDS, SHEET_WORDS } from "./messages";
import { openRows } from "./room";
import { useThread } from "./sheet";

export interface ScopedRequestRoomProps {
  room: PortalRoomOut;
  /** The firm's name as the portal shows it. */
  firm: string;
  /** A server date ("2026-09-18") in the portal's words ("Sep 18"). */
  day: (iso: string) => string;
  /** The open row, if any. */
  expanded: string | null;
  onExpand: (id: string | null) => void;
  /** The file input's accepted types (the portal's upload policy). */
  accept: string;
  /** The 390 layout: one row in full when one is open. */
  mobile?: boolean;
  /** The server's pre-selection for files dropped on the pill (null: the person chooses). */
  suggest: (files: readonly File[]) => Promise<string | null>;
  onUpload: (row: PortalRoomRowOut, files: readonly File[]) => void;
  onWithdraw: (row: PortalRoomRowOut, file: PortalFileOut) => void;
  onComment: (row: PortalRoomRowOut, text: string) => void;
}

function subLine(
  row: PortalRoomRowOut,
  firm: string,
  day: (iso: string) => string,
): string | null {
  const on = row.state_on == null ? null : day(row.state_on);
  switch (row.state) {
    case "uploaded":
      return on === null ? DOCUMENT_WORDS.done : ROOM_WORDS.uploaded(on);
    case "in_review":
      return on === null ? null : ROOM_WORDS.inReview(on, firm);
    case "due":
      return on === null ? null : ROOM_WORDS.due(on);
    case "returned":
      return null; // the red-tint pill says it
  }
}

/** The thread under an open row (SPEC-032 shared comments) and its composer. */
function Thread({
  row,
  firm,
  day,
  onComment,
}: {
  row: PortalRoomRowOut;
  firm: string;
  day: (iso: string) => string;
  onComment: (text: string) => void;
}): JSX.Element {
  const thread = useThread(row.engagement_id, row.id);
  const [text, setText] = useState("");
  const send = (): void => {
    const body = text.trim();
    if (body === "") return;
    onComment(body);
    setText("");
  };
  return (
    <div className="flex flex-col gap-[6px]">
      <ul className="flex flex-col gap-[8px]">
        {(thread.data ?? []).map((c) => (
          <li key={c.id} className="flex flex-col gap-[2px]">
            <span className="text-meta text-ink-3">
              {c.author_side === "firm"
                ? `${c.author_name} · ${firm} · ${day(c.created_at.slice(0, 10))}`
                : `${c.author_name} · ${day(c.created_at.slice(0, 10))}`}
            </span>
            <span className="text-dense leading-[1.5]">{c.text ?? ""}</span>
          </li>
        ))}
      </ul>
      {(row.allowed_actions ?? []).includes("comment") && (
        <div className="flex h-[40px] items-center gap-[8px] rounded-nested bg-nested px-[12px] inset-ring-[0.5px] inset-ring-hair">
          <input
            aria-label={ROOM_WORDS.comment}
            placeholder={ROOM_WORDS.comment}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                send();
              }
            }}
            className="min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-ink-3"
          />
          <button
            type="button"
            aria-label={ROOM_WORDS.send}
            disabled={text.trim() === ""}
            onClick={send}
            className="inline-flex size-[28px] flex-none items-center justify-center rounded-pill bg-card shadow-e1 disabled:text-ink-4"
          >
            <Icon name="arrow-right" size={13} />
          </button>
        </div>
      )}
    </div>
  );
}

function OpenRow({
  row,
  firm,
  day,
  choose,
  onWithdraw,
  onComment,
}: {
  row: PortalRoomRowOut;
  firm: string;
  day: (iso: string) => string;
  choose: () => void;
  onWithdraw: (file: PortalFileOut) => void;
  onComment: (text: string) => void;
}): JSX.Element {
  const allowed = new Set(row.allowed_actions ?? []);
  return (
    <div
      data-open-row={row.id}
      className="mx-[10px] mb-[10px] flex flex-col gap-[10px] rounded-nested bg-shell px-[14px] py-[12px]"
    >
      {row.returned != null && (
        <span className="flex flex-col items-start gap-[5px]">
          <span className="text-dense leading-[1.5] text-ink-2">
            {ROOM_WORDS.returnedNote(row.returned.note, row.returned.by_name)}
          </span>
        </span>
      )}
      {row.guidance != null && row.guidance !== "" && (
        <p className="text-dense leading-[1.55] text-ink-2">{row.guidance}</p>
      )}
      {(row.files ?? []).map((f) => (
        <span key={f.id} className="flex items-center gap-[8px] text-dense">
          <Icon name="file" size={14} className="flex-none text-ink-3" />
          <span className={cn("min-w-0 flex-1 truncate", f.struck === true && "line-through")}>
            {f.size_bytes == null ? f.name : `${f.name} · ${bytes(f.size_bytes)}`}
          </span>
          {f.withdrawable && allowed.has("withdraw") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                onWithdraw(f);
              }}
            >
              {SHEET_WORDS.withdraw}
            </Button>
          )}
        </span>
      ))}
      {allowed.has("upload") && (
        <button
          type="button"
          onClick={choose}
          className="flex h-[72px] items-center justify-center gap-[8px] rounded-nested bg-nested text-dense text-ink-2 inset-ring-1 inset-ring-hair hover:inset-ring-stroke"
        >
          <Icon name="upload" size={14} />
          {ROOM_WORDS.uploadSlot(row.title)}
        </button>
      )}
      <Thread row={row} firm={firm} day={day} onComment={onComment} />
    </div>
  );
}

function Row({
  row,
  firm,
  day,
  open,
  onToggle,
}: {
  row: PortalRoomRowOut;
  firm: string;
  day: (iso: string) => string;
  open: boolean;
  onToggle: () => void;
}): JSX.Element {
  const line = subLine(row, firm, day);
  const done = row.disc === "done";
  return (
    <button
      type="button"
      data-request={row.id}
      data-state={row.state}
      aria-expanded={open}
      onClick={onToggle}
      className={cn(
        "flex min-h-[52px] w-full items-center gap-[12px] bg-card px-[14px] py-[8px] text-left hairline-t hover:bg-band-hd",
        open && "bg-band-hd",
      )}
    >
      <Icon name="file" size={14} className="flex-none text-ink-3" />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="text-body">{row.title}</span>
        {row.state === "returned" ? (
          <span className="inline-flex h-[19px] items-center self-start rounded-pill bg-red-tint px-[8px] text-pill text-red-ink">
            {DOCUMENT_WORDS.returned.pill(row.returned?.reason ?? "other")}
          </span>
        ) : (
          line !== null && <span className="text-meta text-ink-3">{line}</span>
        )}
      </span>
      <StatusDisc state={done ? "done" : "todo"} size={17} />
    </button>
  );
}

/** The room: intro, bands, rows, and the picker for files dropped on the pill. */
export function ScopedRequestRoom({
  room,
  firm,
  day,
  expanded,
  onExpand,
  accept,
  mobile = false,
  suggest,
  onUpload,
  onWithdraw,
  onComment,
}: ScopedRequestRoomProps): JSX.Element {
  const input = useRef<HTMLInputElement>(null);
  const [target, setTarget] = useState<string | null>(null);
  const [picking, setPicking] = useState<{ files: readonly File[]; choice: string | null } | null>(
    null,
  );
  const [withdrawing, setWithdrawing] = useState<{
    row: PortalRoomRowOut;
    file: PortalFileOut;
  } | null>(null);
  const rows = room.bands.flatMap((b) => b.rows);
  const open = openRows(room);
  const share = room.total === 0 ? 0 : Math.round((room.uploaded_count / room.total) * 100);
  const chooseFor = (id: string | null): void => {
    setTarget(id);
    input.current?.click();
  };
  /** Files for the room as a whole: one open request takes them; more, and the person chooses
   * with the server's pre-selection. */
  const placed = (files: readonly File[]): void => {
    if (files.length === 0) return;
    const only = open.length === 1 ? open[0] : undefined;
    if (only !== undefined) {
      onUpload(only, files);
      return;
    }
    if (open.length === 0) return;
    setPicking({ files, choice: null });
    void suggest(files)
      .then((choice) => {
        setPicking((p) => (p === null ? p : { ...p, choice }));
      })
      .catch(() => undefined);
  };
  const shown =
    mobile && expanded !== null
      ? room.bands
          .map((b) => ({ ...b, rows: b.rows.filter((r) => r.id === expanded) }))
          .filter((b) => b.rows.length > 0)
      : room.bands;
  return (
    <div data-room="" className="flex flex-col">
      <input
        ref={input}
        type="file"
        hidden
        multiple
        accept={accept}
        {...(mobile ? { capture: "environment" as const } : {})}
        onChange={(event) => {
          const files = [...(event.target.files ?? [])];
          event.target.value = "";
          const row = rows.find((r) => r.id === target);
          if (row !== undefined) onUpload(row, files);
          else placed(files);
        }}
      />
      <div className="flex flex-col gap-[8px] px-[18px] py-[16px] hairline-b">
        <h2 className="text-title font-medium">{room.engagement_label}</h2>
        <p className="text-dense leading-[1.5] text-ink-2">
          {room.intro ?? ROOM_WORDS.intro(firm, room.organisation_name)}
        </p>
        <div className="flex items-center gap-[12px]">
          <span className="text-body font-medium">
            {ROOM_WORDS.progress(room.uploaded_count, room.total)}
          </span>
          <span
            role="progressbar"
            aria-label={ROOM_WORDS.progress(room.uploaded_count, room.total)}
            aria-valuemin={0}
            aria-valuemax={room.total}
            aria-valuenow={room.uploaded_count}
            className="h-[3px] w-[200px] max-w-[40%] overflow-hidden rounded-[2px] bg-chip"
          >
            <span className="block h-full bg-espresso" style={{ width: `${String(share)}%` }} />
          </span>
          <span className="flex-1" />
          {open.length > 0 && (
            <button
              type="button"
              aria-label={ROOM_WORDS.dropPill}
              onClick={() => {
                chooseFor(null);
              }}
              onDragOver={(event: DragEvent) => {
                event.preventDefault();
              }}
              onDrop={(event: DragEvent) => {
                event.preventDefault();
                placed([...event.dataTransfer.files]);
              }}
              className="inline-flex h-[30px] flex-none items-center gap-[6px] rounded-pill bg-nested px-[12px] text-dense hover:bg-nav-fill"
            >
              <Icon name="upload" size={14} />
              {ROOM_WORDS.dropPill}
            </button>
          )}
        </div>
      </div>
      {room.complete && (
        <div
          role="status"
          className="mx-[10px] mt-[10px] flex items-center gap-[8px] rounded-nested bg-green-tint px-[14px] py-[10px] text-dense text-green-ink"
        >
          <StatusDisc state="done" size={15} />
          {ROOM_WORDS.complete(firm, room.organisation_name)}
        </div>
      )}
      <div className="flex flex-col">
        {shown.map((band) => (
          <section key={band.code} aria-label={band.label} data-part="band">
            <div className="flex h-[32px] items-center gap-[8px] bg-nested px-[14px]">
              <Icon name="folder" size={12} className="text-ink-3" />
              <span className="min-w-0 flex-1 text-dense font-medium text-ink-2">
                {band.label}
              </span>
              <span className="text-meta text-ink-3">
                {ROOM_WORDS.bandCount(band.uploaded, band.total)}
              </span>
            </div>
            {band.rows.map((row) => (
              <div key={row.id}>
                <Row
                  row={row}
                  firm={firm}
                  day={day}
                  open={expanded === row.id}
                  onToggle={() => {
                    onExpand(expanded === row.id ? null : row.id);
                  }}
                />
                {expanded === row.id && (
                  <OpenRow
                    row={row}
                    firm={firm}
                    day={day}
                    choose={() => {
                      chooseFor(row.id);
                    }}
                    onWithdraw={(file) => {
                      setWithdrawing({ row, file });
                    }}
                    onComment={(text) => {
                      onComment(row, text);
                    }}
                  />
                )}
              </div>
            ))}
          </section>
        ))}
      </div>
      <Dialog
        open={picking !== null}
        onOpenChange={(next) => {
          if (!next) setPicking(null);
        }}
        title={ROOM_WORDS.pickerTitle}
        action={
          <Button
            variant="primary"
            size="md"
            disabled={picking?.choice == null}
            onClick={() => {
              const row = open.find((r) => r.id === picking?.choice);
              if (row !== undefined && picking !== null) onUpload(row, picking.files);
              setPicking(null);
            }}
          >
            {ROOM_WORDS.pickerUpload}
          </Button>
        }
      >
        <RadioGroup
          label={ROOM_WORDS.pickerTitle}
          options={open.map((r) => ({ value: r.id, label: r.title }))}
          {...(picking?.choice == null ? {} : { value: picking.choice })}
          onChange={(choice) => {
            setPicking((p) => (p === null ? p : { ...p, choice }));
          }}
        />
      </Dialog>
      <ConfirmDialog
        open={withdrawing !== null}
        onOpenChange={(next) => {
          if (!next) setWithdrawing(null);
        }}
        title={SHEET_WORDS.withdraw}
        confirmLabel={SHEET_WORDS.withdraw}
        cancelLabel={SHEET_WORDS.cancel}
        onConfirm={() => {
          if (withdrawing !== null) onWithdraw(withdrawing.row, withdrawing.file);
          setWithdrawing(null);
        }}
      >
        {SHEET_WORDS.withdrawConfirm(firm)}
      </ConfirmDialog>
    </div>
  );
}
