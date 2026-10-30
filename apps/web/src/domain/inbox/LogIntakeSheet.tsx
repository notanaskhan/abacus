import { logIntake, logIntakeFile, type LogIntakeIn } from "@abacus/api-client";
import {
  inboxSummaryQueryKey,
  listClientsOptions,
  listContactsOptions,
  listThreadsQueryKey,
} from "@abacus/api-client/query";
import { Button, Fieldset, Label, SheetModal, Segmented, ValueRow } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { LOG_COPY as COPY } from "./copy";

// Log received documents (DV-1; docs/screens/INB-02.md § Log received documents; N-01-T09's
// `POST /v1/inbox/intake` and `…/{message_id}/files`; made live by N-01-T23): the O3 sheet over
// INB-01 at `?ov=log-intake`. A person logs what the firm received outside the portal: the batch
// first (one thread, one message, matched to the client when one is chosen, else it waits in the
// Inbox unmatched), then each file, scanned before it is stored. "Log {n}" in the header.

export const MAX_FILES = 20;
export const MAX_BYTES = 50 * 1024 * 1024;
const VIA: readonly LogIntakeIn["received_via"][] = ["email", "mail", "fax", "in_person", "other"];

/** `YYYY-MM-DD` of an instant in the viewer's own calendar. */
function dayOf(at: Date): string {
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${String(at.getFullYear())}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
}

function errorCode(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export interface LogIntakeSheetProps {
  open: boolean;
  /** "Logged as {viewer}." */
  viewer: string;
  onClose: () => void;
  /** After the batch and its files are logged: the new message, for INB-01 to select. */
  onLogged?: (messageId: string) => void;
}

export function LogIntakeSheet({
  open,
  viewer,
  onClose,
  onLogged,
}: LogIntakeSheetProps): JSX.Element {
  const queryClient = useQueryClient();
  const now = useNow();
  const [files, setFiles] = useState<File[]>([]);
  const [clientId, setClientId] = useState("");
  const [via, setVia] = useState<LogIntakeIn["received_via"]>("email");
  const [contactId, setContactId] = useState("");
  const [fromText, setFromText] = useState("");
  const [day, setDay] = useState(dayOf(now));
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const clients = useQuery({ ...listClientsOptions({ query: { limit: 100 } }), enabled: open });
  const contacts = useQuery({
    ...listContactsOptions({ path: { client_id: clientId } }),
    enabled: open && clientId !== "",
  });
  const tooMany = files.length > MAX_FILES;
  const tooLarge = files.find((f) => f.size > MAX_BYTES);
  const ready =
    files.length > 0 &&
    !tooMany &&
    tooLarge === undefined &&
    subject.trim() !== "" &&
    /^\d{4}-\d{2}-\d{2}$/.test(day);

  const submit = async (): Promise<void> => {
    if (!ready) return;
    setBusy(true);
    setProblem(null);
    try {
      const body: LogIntakeIn = {
        received_via: via,
        // Today is the instant now; an earlier day is that day's noon (the sheet asks for a day).
        received_at: day === dayOf(now) ? now.toISOString() : `${day}T12:00:00`,
        subject: subject.trim(),
        ...(clientId === "" ? {} : { client_id: clientId }),
        ...(contactId !== ""
          ? { from_contact_id: contactId }
          : fromText.trim() === ""
            ? {}
            : { from_display: fromText.trim() }),
        ...(note.trim() === "" ? {} : { note: note.trim() }),
      };
      const { data } = await logIntake({
        body,
        headers: { "Idempotency-Key": crypto.randomUUID() },
        throwOnError: true,
      });
      for (const file of files) {
        await logIntakeFile({
          path: { message_id: data.message_id },
          query: { filename: file.name },
          body: file as never,
          bodySerializer: null,
          headers: {
            "Content-Type": file.type || "application/octet-stream",
            "Idempotency-Key": crypto.randomUUID(),
          },
          throwOnError: true,
        });
      }
      void queryClient.invalidateQueries({ queryKey: listThreadsQueryKey() });
      void queryClient.invalidateQueries({ queryKey: inboxSummaryQueryKey() });
      onLogged?.(data.message_id);
      onClose();
    } catch (error) {
      const code = errorCode(error);
      setProblem(
        code === "unsupported_media_type"
          ? COPY.errors.type
          : code === "file_too_large"
            ? COPY.errors.size
            : code === "scanner_unavailable"
              ? COPY.errors.scanner
              : COPY.errors.failed,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.title}
      dirty={files.length > 0 || subject !== "" || note !== ""}
      action={
        <Button
          variant="primary"
          size="sm"
          disabled={!ready || busy}
          onClick={() => {
            void submit();
          }}
        >
          {COPY.log(files.length)}
        </Button>
      }
    >
      <div data-sheet="log-intake" className="flex flex-col gap-[12px] p-[16px] text-body">
        <div className="flex flex-col gap-[6px]">
          <Label htmlFor="log-intake-files">{COPY.files}</Label>
          <input
            id="log-intake-files"
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.heic,.xlsx,.docx,.csv"
            onChange={(e) => {
              setFiles(Array.from(e.target.files ?? []));
            }}
          />
          <span className="text-[11.5px] text-ink-3">{COPY.filesHelp}</span>
          {tooMany && (
            <span role="alert" className="text-red-ink">
              {COPY.errors.count}
            </span>
          )}
          {tooLarge !== undefined && (
            <span role="alert" className="text-red-ink">
              {COPY.errors.size}
            </span>
          )}
        </div>
        <Fieldset flush>
          <ValueRow
            kind="select"
            label={COPY.client}
            value={clientId}
            placeholder={COPY.select}
            help={COPY.clientHelp}
            options={(clients.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }))}
            onChange={(next) => {
              setClientId(next);
              setContactId("");
            }}
          />
          <div className="flex min-h-[34px] items-center justify-between gap-[10px] px-[12px]">
            <span className="text-ink-2">{COPY.receivedVia}</span>
            <Segmented
              label={COPY.receivedVia}
              size="small"
              options={VIA.map((v) => ({ label: COPY.via[v] }))}
              active={COPY.via[via]}
              onChange={(label) => {
                const next = VIA.find((v) => COPY.via[v] === label);
                if (next !== undefined) setVia(next);
              }}
            />
          </div>
          {clientId !== "" && (contacts.data?.items ?? []).length > 0 ? (
            <ValueRow
              kind="select"
              label={COPY.from}
              value={contactId}
              placeholder={COPY.select}
              options={(contacts.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }))}
              onChange={setContactId}
            />
          ) : (
            <ValueRow
              kind="text"
              label={COPY.from}
              value={fromText}
              placeholder={COPY.select}
              onChange={setFromText}
            />
          )}
          <ValueRow kind="text" label={COPY.received} value={day} onChange={setDay} />
          <ValueRow
            kind="text"
            label={COPY.subject}
            placeholder={COPY.required}
            value={subject}
            onChange={setSubject}
          />
          <ValueRow kind="paragraph" label={COPY.note} value={note} onChange={setNote} rows={3} />
        </Fieldset>
        {problem !== null && (
          <p role="alert" className="text-body text-red-ink">
            {problem}
          </p>
        )}
        <p className="text-[11.5px] text-ink-3">{COPY.footer(viewer)}</p>
      </div>
    </SheetModal>
  );
}
