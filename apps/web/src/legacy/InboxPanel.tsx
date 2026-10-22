import type { FileMatchOut, InboxFileOut, RequestItemOut } from "@abacus/api-client";
import { addToInbox } from "@abacus/api-client";
import {
  assignInboxFileMutation,
  discardMutation,
  inboxMatchesOptions,
  inboxOptions,
  inboxQueryKey,
  listRequestItemsQueryKey,
} from "@abacus/api-client/query";
import { AiTag, Button, Label, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { InboxAIMatch } from "./InboxAIMatch";
import { reasonLabel } from "./matchingMessages";

const ACCEPT = ".pdf,.xlsx,.xls,.docx,.doc,.csv,.png,.jpg,.jpeg";
const MESSAGES: Record<string, string> = {
  upload_too_large: "The file is over 25 MB.",
  upload_type_not_allowed: "Only PDF, Excel, Word, CSV, PNG and JPEG files can be uploaded.",
  // SPEC-029 AC-1: the malware scan refused it; nothing was stored.
  file_refused:
    "We couldn't accept this file. Please save it again from where it came from and upload the new copy.",
  upload_empty: "The file is empty.",
  duplicate_upload: "This file is already waiting here, or already on that request.",
  item_closed: "That request no longer takes files.",
  inbox_file_gone: "Someone already matched or removed this file.",
  forbidden: "You can't add files to that request.",
};

function message(error: unknown): string {
  const code = errorMessage(error);
  return MESSAGES[code] ?? code;
}

type Dropped = { name: string; state: "uploading" | "done" | "failed"; message?: string };

/** SPEC-023: files dropped at the engagement level, each matched to a request by a person. */
export function InboxPanel({
  engagementId,
  items,
  firm,
}: {
  engagementId: string;
  items: RequestItemOut[];
  // SPEC-033 (TASK-066): the firm's view, with the matcher's proposals; absent for clients.
  firm?: { canRequestMatch: boolean };
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const files = useQuery({ ...inboxOptions(path), retry: false });
  const matches = useQuery({
    ...inboxMatchesOptions(path),
    retry: false,
    enabled: firm !== undefined && (files.data?.length ?? 0) > 0,
    refetchInterval: (query) =>
      query.state.data?.some((m) => m.status === "running") === true ? 4000 : false,
  });
  const matchOf = new Map((matches.data ?? []).map((m) => [m.inbox_file_id, m]));
  const [dropped, setDropped] = useState<Dropped[]>([]);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: inboxQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
  };

  const send = async (chosen: File[]): Promise<void> => {
    setDropped(chosen.map((f) => ({ name: f.name, state: "uploading" })));
    for (const [index, file] of chosen.entries()) {
      let next: Dropped;
      try {
        await addToInbox({
          path: { engagement_id: engagementId },
          query: { filename: file.name },
          body: file as never,
          bodySerializer: null,
          headers: { "Content-Type": file.type || "application/octet-stream" },
          throwOnError: true,
        });
        next = { name: file.name, state: "done" };
      } catch (error) {
        next = { name: file.name, state: "failed", message: message(error) };
      }
      setDropped((current) => current.map((d, i) => (i === index ? next : d)));
    }
    refresh();
  };

  if (files.isError) return <></>; // not allowed here: nothing to show
  const waiting = files.data ?? [];
  return (
    <Panel
      title="Inbox"
      action={
        waiting.length > 0 ? (
          <StatusPill tone="warning">{`${String(waiting.length)} to match`}</StatusPill>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-1">
        <Label htmlFor={`inbox-${engagementId}`}>Add several files at once</Label>
        <input
          id={`inbox-${engagementId}`}
          type="file"
          multiple
          accept={ACCEPT}
          className="text-body"
          onChange={(event) => {
            const chosen = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (chosen.length > 0) void send(chosen);
          }}
        />
      </div>
      {dropped.length > 0 && (
        <ul aria-label="Files being added" className="flex flex-col gap-1 text-body">
          {dropped.map((d, index) => (
            <li key={`${d.name}-${String(index)}`} className="flex items-center gap-2">
              <span>{d.name}</span>
              {d.state === "uploading" ? (
                <StatusPill tone="info">Adding…</StatusPill>
              ) : d.state === "done" ? (
                <StatusPill tone="success">Added</StatusPill>
              ) : (
                <span role="alert" className="text-danger">
                  {d.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {files.isPending ? (
        <Skeleton className="h-16" />
      ) : waiting.length === 0 ? (
        <p className="text-body text-ink-3">Nothing waiting to be matched.</p>
      ) : (
        <ul aria-label="Files to match" className="flex flex-col divide-y divide-hair">
          {waiting.map((file) => (
            <InboxRow
              key={file.id}
              engagementId={engagementId}
              file={file}
              items={items}
              onDone={refresh}
              firm={
                firm === undefined
                  ? undefined
                  : { match: matchOf.get(file.id), canRequest: firm.canRequestMatch }
              }
            />
          ))}
        </ul>
      )}
    </Panel>
  );
}

function InboxRow({
  engagementId,
  file,
  items,
  onDone,
  firm,
}: {
  engagementId: string;
  file: InboxFileOut;
  items: RequestItemOut[];
  onDone: () => void;
  firm: { match: FileMatchOut | undefined; canRequest: boolean } | undefined;
}): JSX.Element {
  const [chosen, setChosen] = useState("");
  const after = { onSuccess: onDone, onError: onDone };
  const assign = useMutation({ ...assignInboxFileMutation(), ...after });
  const discard = useMutation({ ...discardMutation(), ...after });
  const describe = new Map(items.map((i) => [i.id, i.description]));
  const open = items.filter((i) =>
    ["draft", "requested", "uploaded", "returned"].includes(i.status),
  );
  const ids = { engagement_id: engagementId, file_id: file.id };
  const failed = assign.error ?? discard.error;
  const busy = assign.isPending || discard.isPending;
  const to = (itemId: string): void => {
    // SPEC-033 AC-6: which suggestion was followed, and its rank.
    const rank = file.suggestions.findIndex((s) => s.request_item_id === itemId);
    const followed = file.suggestions[rank];
    assign.mutate({
      path: ids,
      body: {
        request_item_id: itemId,
        followed_suggestion: followed !== undefined,
        ...(followed !== undefined
          ? { suggestion_source: followed.source ?? "file_name", suggestion_rank: rank + 1 }
          : {}),
      },
    });
  };
  return (
    <li className="flex flex-col gap-2 py-3 text-body">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium break-all">{file.file_name}</span>
        <span className="text-meta text-ink-3">
          {file.uploaded_by_staff
            ? "Added by the audit team"
            : `Added by ${file.uploaded_by_name || "the client"}`}
        </span>
      </div>
      {file.note !== null && <p className="text-meta text-ink-3">{file.note}</p>}
      {file.suggestions.length > 0 ? (
        <ul className="flex flex-col gap-2" aria-label={`Suggestions for ${file.file_name}`}>
          {file.suggestions.map((s) => (
            <li key={s.request_item_id} className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                title={`Matched: ${s.matched.join(", ") || "a known document type"}`}
                onClick={() => {
                  to(s.request_item_id);
                }}
              >
                {`${describe.get(s.request_item_id) ?? "Request"} · ${String(s.score)}%`}
              </Button>
              {/* SPEC-033 (TASK-066): the matcher's pick; clients see "Suggested", no AI words. */}
              {s.source === "matcher" &&
                (firm !== undefined ? (
                  <AiTag />
                ) : (
                  <span className="text-meta text-amber-ink">Suggested</span>
                ))}
              {/* SPEC-033 (TASK-064): why, in fixed words. */}
              {s.source === "content" && (
                <span className="text-meta text-amber-ink">From the file&apos;s contents</span>
              )}
              {(s.reasons ?? [])
                .filter((r) => r.code !== "file_name" || s.source === "content")
                .map((r) => (
                  <span
                    key={`${r.code}-${r.value ?? ""}`}
                    className="rounded-pill bg-sunken px-2 py-0.5 text-meta text-ink-3"
                  >
                    {reasonLabel(r)}
                  </span>
                ))}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-meta text-ink-3">No suggestion: choose the request below.</p>
      )}
      {firm !== undefined && (
        <InboxAIMatch
          engagementId={engagementId}
          fileId={file.id}
          match={firm.match}
          items={items}
          canRequest={firm.canRequest}
        />
      )}
      <div className="flex flex-wrap items-end gap-2">
        <select
          aria-label={`Request for ${file.file_name}`}
          value={chosen}
          onChange={(event) => {
            setChosen(event.target.value);
          }}
          className="h-8 rounded-[var(--radius-control)] border border-hair bg-surface px-2 text-body"
        >
          <option value="">Choose a request…</option>
          {open.map((i) => (
            <option key={i.id} value={i.id}>
              {i.description}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          disabled={chosen === "" || busy}
          onClick={() => {
            to(chosen);
          }}
        >
          Match
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => {
            discard.mutate({ path: ids });
          }}
        >
          Remove
        </Button>
      </div>
      {failed !== null && (
        <p role="alert" className="text-danger">
          {message(failed)}
        </p>
      )}
    </li>
  );
}
