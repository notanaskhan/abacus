import type {
  ClientContactOut,
  ClientResponseOut,
  HistoryEntryOut,
  RequestItemOut,
} from "@abacus/api-client";
import { upload } from "@abacus/api-client";
import {
  assignToClientMutation,
  clientContactsOptions,
  clientViewOptions,
  clientViewQueryKey,
  getEngagementOptions,
  listRequestItemsOptions,
  listRequestItemsQueryKey,
  listUploadsOptions,
  listUploadsQueryKey,
  meOptions,
  clientDoneOptions,
  clientDoneQueryKey,
  clientRespondMutation,
  clientResponsesOptions,
  clientResponsesQueryKey,
  clientWithdrawMutation,
  markDoneMutation,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  Button,
  bytes,
  DateText,
  Dialog,
  EmptyState,
  Label,
  Panel,
  Skeleton,
  StatusPill,
  statusWord,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { PortalBrand } from "../shell/PortalBrand";
import { useSignedIn } from "../app-core/auth";
import { ClientUploadChecks } from "./CheckResults";
import { CommentThread } from "./CommentThread";
import { ConnectionPanel } from "./ConnectionPanel";
import { EvidencePreview } from "./EvidencePreview";
import { InboxPanel } from "./InboxPanel";
import { gapMessage, outcomeLabel, providedBy, providedMessage } from "./clientHubMessages";
import { longDate } from "./importMessages";

// SPEC-020 AC-9: refusals in plain words (the API returns fixed codes).
const UPLOAD_ERRORS: Record<string, string> = {
  upload_too_large: "The file is over 25 MB.",
  upload_type_not_allowed: "Only PDF, Excel, Word, CSV, PNG and JPEG files can be uploaded.",
  // SPEC-029 AC-1: the malware scan refused it; nothing was stored.
  file_refused:
    "We couldn't accept this file. Please save it again from where it came from and upload the new copy.",
  upload_empty: "The file is empty.",
  duplicate_upload: "This file is already uploaded to this request.",
  item_closed: "This request no longer takes files.",
  forbidden: "You can't upload to this request.",
};
const ACCEPT = ".pdf,.xlsx,.xls,.docx,.doc,.csv,.png,.jpg,.jpeg";

function uploadError(error: unknown): string {
  const code = errorMessage(error);
  return UPLOAD_ERRORS[code] ?? code;
}

/** SPEC-020 AC-1: a client's view of one engagement — its requests by area, with uploads. */
export function ClientEngagement({ engagementId }: { engagementId: string }): JSX.Element {
  const signedIn = useSignedIn(`/client/engagements/${engagementId}`);
  const path = { path: { engagement_id: engagementId } };
  const engagement = useQuery({ ...getEngagementOptions(path), enabled: signedIn });
  const items = useQuery({ ...listRequestItemsOptions(path), enabled: signedIn });
  // Only client admins may read contacts (and assign): a refusal means a contributor.
  const contacts = useQuery({ ...clientContactsOptions(path), retry: false, enabled: signedIn });
  const contributors = (contacts.data ?? []).filter(
    (c) => c.kind === "member" && c.role === "client_contributor",
  );
  const isAdmin = contacts.isSuccess;
  const me = useQuery({ ...meOptions(), enabled: signedIn });
  const active = me.data?.active_tenant_id;
  const firmName =
    me.data?.memberships.find((m) => m.tenant_id === active)?.firm_name ?? "your audit firm";

  // SPEC-042 (TASK-106): what the client said doesn't apply, and whether the list is marked done.
  const responses = useQuery({ ...clientResponsesOptions(path), retry: false, enabled: signedIn });
  const doneMark = useQuery({ ...clientDoneOptions(path), retry: false, enabled: signedIn });
  const ignoredBy = new Map((responses.data ?? []).map((r) => [r.request_item_id, r]));
  const all = items.data ?? [];
  const doneCount = all.filter(
    (i) => ignoredBy.has(i.id) || ["uploaded", "received", "not_applicable"].includes(i.status),
  ).length;

  const areas = new Map<string, RequestItemOut[]>();
  // SPEC-031 Q5: what blocks fieldwork comes first.
  const ordered = [...(items.data ?? [])].sort(
    (a, b) => Number(b.blocks_fieldwork === true) - Number(a.blocks_fieldwork === true),
  );
  for (const item of ordered) {
    areas.set(item.audit_area, [...(areas.get(item.audit_area) ?? []), item]);
  }

  return (
    <div className="min-h-screen bg-shell">
      <header className="flex h-[46px] items-center justify-between border-b-[0.5px] border-hair bg-card px-4">
        <PortalBrand />
        <span className="flex items-center gap-3">
          <Link to="/client" className="text-body text-espresso hover:underline">
            Your engagements
          </Link>
        </span>
      </header>
      <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
        {engagement.isPending ? (
          <Skeleton className="h-12" />
        ) : engagement.isError ? (
          <Alert title="Couldn't load this engagement">{errorMessage(engagement.error)}</Alert>
        ) : (
          <div>
            <h1 className="text-dashboard">{engagement.data.name}</h1>
            <p className="text-body text-ink-3 tabular-nums">
              With {firmName} · {engagement.data.client_name} ·{" "}
              {engagement.data.fiscal_period_start} to {engagement.data.fiscal_period_end}
            </p>
          </div>
        )}
        {all.length > 0 && (
          <DoneBar
            engagementId={engagementId}
            done={doneCount}
            total={all.length}
            marked={doneMark.data ?? null}
            canMark={isAdmin}
          />
        )}
        {isAdmin && <ConnectionPanel engagementId={engagementId} firmName={firmName} canConnect />}
        {items.data !== undefined && <InboxPanel engagementId={engagementId} items={items.data} />}
        {items.isPending ? (
          <Skeleton className="h-40" />
        ) : items.isError ? (
          <Alert title="Couldn't load your requests">{errorMessage(items.error)}</Alert>
        ) : areas.size === 0 ? (
          <EmptyState title="Nothing requested yet">
            {isAdmin
              ? "Your auditor hasn't shared any requests yet."
              : "Nothing is assigned to you yet. Your company's administrator assigns requests."}
          </EmptyState>
        ) : (
          [...areas].map(([area, list]) => (
            <Panel key={area} title={area}>
              <ul className="flex flex-col divide-y divide-hair">
                {list.map((item) => (
                  <ClientItem
                    key={item.id}
                    item={item}
                    ignored={ignoredBy.get(item.id)}
                    contributors={isAdmin ? contributors : null}
                    me={me.data?.user_id}
                  />
                ))}
              </ul>
            </Panel>
          ))
        )}
      </main>
    </div>
  );
}

type FileState = { name: string; state: "uploading" | "done" | "failed"; message?: string };

/** SPEC-031 AC-1: why we ask, what good looks like and what's still needed, as the firm wrote
 * them (or fixed copy); shown only when present. */
function Guidance({ item }: { item: RequestItemOut }): JSX.Element | null {
  const parts: [string, string | null | undefined][] = [
    ["Why we need it", item.why],
    ["What good looks like", item.good_looks_like],
    ["Still needed", item.still_needed],
  ];
  const shown = parts.filter(([, text]) => text != null && text !== "");
  if (shown.length === 0) return null;
  return (
    <dl className="flex flex-col gap-1 text-body">
      {shown.map(([label, text]) => (
        <div key={label}>
          <dt className="font-medium">{label}</dt>
          <dd className="whitespace-pre-line text-ink-3">{text}</dd>
        </div>
      ))}
    </dl>
  );
}

function Outcome({ entry }: { entry: HistoryEntryOut | undefined }): JSX.Element | null {
  if (entry === undefined) return null;
  return (
    <span className="flex flex-col">
      <span className={entry.outcome === "sent_back" ? "text-danger" : undefined}>
        {outcomeLabel(entry)}
      </span>
      {entry.outcome === "sent_back" && entry.note != null && (
        <span className="text-ink">&ldquo;{entry.note}&rdquo;</span>
      )}
    </span>
  );
}

function ClientItem({
  item,
  ignored,
  contributors,
  me,
}: {
  item: RequestItemOut;
  ignored: ClientResponseOut | undefined;
  contributors: ClientContactOut[] | null;
  me: string | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<FileState[]>([]);
  const [previewing, setPreviewing] = useState<string | null>(null);
  // SPEC-032 (TASK-063): the request's thread, and one version's.
  const [talking, setTalking] = useState(false);
  const [versionThread, setVersionThread] = useState<string | null>(null);
  // SPEC-042: the client's own words, never the firm's states.
  const status = statusWord(
    "clientRequest",
    ignored !== undefined ? "not_applicable" : item.status,
  );
  const ids = { engagement_id: item.engagement_id, item_id: item.id };
  // SPEC-031 AC-4, AC-5, AC-7: provided, the bank statement gap and the history. Without it the
  // row still works as before (uploads only).
  const view = useQuery({ ...clientViewOptions({ path: ids }), retry: false });
  const provided = view.data?.provided ?? null;
  const gap = view.data?.gap != null ? gapMessage(view.data.gap) : null;
  const history = new Map((view.data?.history ?? []).map((h) => [h.evidence_version_id, h]));
  const takesFiles =
    ignored === undefined &&
    provided === null &&
    ["requested", "uploaded", "returned"].includes(item.status);
  const uploads = useQuery({ ...listUploadsOptions({ path: ids }), enabled: open });
  const uploaded = new Set((uploads.data ?? []).map((u) => u.evidence_version_id));
  const fromSystem = (view.data?.history ?? []).filter(
    (h) => h.added_by === "firm" && !uploaded.has(h.evidence_version_id),
  );
  const assign = useMutation({
    ...assignToClientMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: item.engagement_id } }),
      });
    },
  });

  const send = async (chosen: File[]): Promise<void> => {
    setOpen(true);
    setFiles(chosen.map((f) => ({ name: f.name, state: "uploading" })));
    for (const [index, file] of chosen.entries()) {
      let next: FileState;
      try {
        await upload({
          path: ids,
          query: { filename: file.name },
          body: file as never,
          bodySerializer: null,
          headers: { "Content-Type": file.type || "application/octet-stream" },
          throwOnError: true,
        });
        next = { name: file.name, state: "done" };
      } catch (error) {
        next = { name: file.name, state: "failed", message: uploadError(error) };
      }
      setFiles((current) => current.map((f, i) => (i === index ? next : f)));
    }
    void queryClient.invalidateQueries({ queryKey: listUploadsQueryKey({ path: ids }) });
    void queryClient.invalidateQueries({ queryKey: clientViewQueryKey({ path: ids }) });
    void queryClient.invalidateQueries({
      queryKey: listRequestItemsQueryKey({ path: { engagement_id: item.engagement_id } }),
    });
  };

  const inputId = `upload-${item.id}`;
  return (
    <li id={`request-${item.id}`} className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="font-medium whitespace-pre-line">{item.description}</p>
        <span className="flex items-center gap-2">
          {item.blocks_fieldwork === true && <Badge tone="warning">Blocks fieldwork</Badge>}
          <StatusPill tone={status.tone}>{status.label}</StatusPill>
        </span>
      </div>
      {item.due_on != null && <p className="text-body text-ink-3">Due {longDate(item.due_on)}</p>}
      <Guidance item={item} />
      <NotApplicable item={item} ignored={ignored} />
      {provided !== null && <p className="text-body text-ok">{providedMessage(provided)}</p>}
      {gap !== null && <p className="text-body">{gap}</p>}
      <div className="flex flex-wrap items-center gap-3">
        {takesFiles && (
          <>
            <Label htmlFor={inputId} className="sr-only">
              Upload files for {item.description}
            </Label>
            <input
              id={inputId}
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
          </>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={open}
          onClick={() => {
            setOpen((o) => !o);
          }}
        >
          {open ? "Hide history" : "Show history"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={talking}
          onClick={() => {
            setTalking((t) => !t);
          }}
        >
          Comments ({item.comment_count ?? 0})
          {item.unread_comments === true && (
            <span
              aria-label="Unread comments"
              className="ml-1 inline-block size-2 rounded-full bg-espresso"
            />
          )}
        </Button>
        {contributors !== null && (
          <span className="ml-auto flex items-center gap-2 text-body">
            <Label htmlFor={`assignee-${item.id}`}>Assigned to</Label>
            <select
              id={`assignee-${item.id}`}
              value={item.client_assignee_user_id ?? ""}
              disabled={assign.isPending}
              onChange={(event) => {
                assign.mutate({
                  path: ids,
                  body: { user_id: event.target.value === "" ? null : event.target.value },
                });
              }}
              className="h-8 rounded-[var(--radius-control)] border border-hair bg-surface px-2 text-body"
            >
              <option value="">No one</option>
              {contributors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name ?? "Contributor"}
                </option>
              ))}
            </select>
          </span>
        )}
      </div>
      {talking && (
        <CommentThread
          ids={{ engagementId: item.engagement_id, itemId: item.id }}
          me={me}
          side="client"
          canShare={false}
          label={`Comments on ${item.description}`}
        />
      )}
      {assign.isError && (
        <p role="alert" className="text-body text-danger">
          {errorMessage(assign.error)}
        </p>
      )}
      {files.length > 0 && (
        <ul aria-label="Files being uploaded" className="flex flex-col gap-1 text-body">
          {files.map((f, index) => (
            <li key={`${f.name}-${String(index)}`} className="flex items-center gap-2">
              <span>{f.name}</span>
              {f.state === "uploading" ? (
                <StatusPill tone="info">Uploading…</StatusPill>
              ) : f.state === "done" ? (
                <StatusPill tone="success">Uploaded</StatusPill>
              ) : (
                <span role="alert" className="text-danger">
                  {f.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {open &&
        (uploads.isPending ? (
          <Skeleton className="h-8" />
        ) : uploads.isError ? (
          <p className="text-body text-danger">{errorMessage(uploads.error)}</p>
        ) : uploads.data.length === 0 && fromSystem.length === 0 ? (
          <p className="text-body text-ink-3">No files uploaded yet.</p>
        ) : (
          <ul aria-label="Uploaded files" className="flex flex-col gap-1 text-body">
            {fromSystem.map((h) => (
              <li key={h.evidence_version_id} className="flex flex-wrap gap-x-2 text-ink-3">
                <span className="text-ink">{providedBy(provided)}</span>
                <span>
                  · <DateText value={h.added_at} kind="dateTime" />
                </span>
                <Outcome entry={h} />
              </li>
            ))}
            {uploads.data.map((u) => (
              <li key={u.evidence_version_id} className="flex flex-wrap gap-x-2 text-ink-3">
                <span className="text-ink">{u.file_name}</span>
                <span className="tabular-nums">{bytes(u.size_bytes)}</span>
                <span>
                  {u.on_behalf === true
                    ? "Added by your auditor"
                    : u.uploaded_by_name || "Someone"}{" "}
                  · <DateText value={u.uploaded_at} kind="dateTime" />
                </span>
                <Outcome entry={history.get(u.evidence_version_id)} />
                <button
                  type="button"
                  className="text-espresso hover:underline"
                  onClick={() => {
                    setVersionThread(
                      versionThread === u.evidence_version_id ? null : u.evidence_version_id,
                    );
                  }}
                >
                  Comments
                </button>
                {versionThread === u.evidence_version_id && (
                  <div className="w-full">
                    <CommentThread
                      ids={{
                        engagementId: item.engagement_id,
                        itemId: item.id,
                        versionId: u.evidence_version_id,
                      }}
                      me={me}
                      side="client"
                      canShare={false}
                      label={`Comments on ${u.file_name}`}
                    />
                  </div>
                )}
                <button
                  type="button"
                  className="text-espresso hover:underline"
                  onClick={() => {
                    setPreviewing(u.evidence_version_id);
                  }}
                >
                  Preview
                </button>
                <ClientUploadChecks
                  ids={{
                    engagementId: item.engagement_id,
                    itemId: item.id,
                    versionId: u.evidence_version_id,
                  }}
                  uploadedAt={u.uploaded_at}
                  replace={
                    takesFiles ? (
                      <Label htmlFor={inputId} className="cursor-pointer text-meta text-espresso">
                        Replace file
                      </Label>
                    ) : null
                  }
                />
              </li>
            ))}
          </ul>
        ))}
      {/* SPEC-029 AC-12 (TASK-056): the client looks at their own upload without downloading. */}
      <Dialog
        open={previewing !== null}
        onOpenChange={(next) => {
          if (!next) setPreviewing(null);
        }}
        title="Preview"
      >
        {previewing !== null && (
          <EvidencePreview
            source={{
              kind: "upload",
              engagementId: item.engagement_id,
              itemId: item.id,
              versionId: previewing,
            }}
          />
        )}
      </Dialog>
    </li>
  );
}

const REASONS = [
  ["not_this_year", "Not applicable this year"],
  ["sent_another_way", "Already sent another way"],
  ["dont_have", "I don't have this"],
] as const;

/** SPEC-042 AC-1, AC-2: "This doesn't apply" with a reason (and a note), or taking it back. */
function NotApplicable({
  item,
  ignored,
}: {
  item: RequestItemOut;
  ignored: ClientResponseOut | undefined;
}): JSX.Element | null {
  const queryClient = useQueryClient();
  const ids = { engagement_id: item.engagement_id, item_id: item.id };
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState<(typeof REASONS)[number][0]>("not_this_year");
  const [note, setNote] = useState("");
  const refresh = (): void => {
    const path = { path: { engagement_id: item.engagement_id } };
    void queryClient.invalidateQueries({ queryKey: clientResponsesQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: clientDoneQueryKey(path) });
  };
  const respond = useMutation({
    ...clientRespondMutation(),
    onSuccess: () => {
      setAsking(false);
      setNote("");
      refresh();
    },
  });
  const withdraw = useMutation({ ...clientWithdrawMutation(), onSuccess: refresh });
  if (ignored !== undefined) {
    const label = REASONS.find(([k]) => k === ignored.reason)?.[1] ?? "Doesn't apply";
    return (
      <p className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-2">
        {`You said: ${label}`}
        {ignored.note != null && <span className="text-ink-3">{`· ${ignored.note}`}</span>}
        <Button
          size="sm"
          variant="ghost"
          disabled={withdraw.isPending}
          onClick={() => {
            withdraw.mutate({ path: ids });
          }}
        >
          Undo
        </Button>
      </p>
    );
  }
  if (!["requested", "returned"].includes(item.status)) return null;
  if (!asking) {
    return (
      <div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setAsking(true);
          }}
        >
          This doesn't apply…
        </Button>
      </div>
    );
  }
  return (
    <fieldset className="flex flex-col gap-2 rounded-nested bg-shell p-3">
      <legend className="sr-only">{`Why ${item.description} doesn't apply`}</legend>
      {REASONS.map(([value, label]) => (
        <label key={value} className="flex items-center gap-2 text-[13px]">
          <input
            type="radio"
            name={`reason-${item.id}`}
            checked={reason === value}
            onChange={() => {
              setReason(value);
            }}
          />
          {label}
        </label>
      ))}
      <input
        aria-label="A note for your auditor (optional)"
        placeholder="A note for your auditor (optional)"
        value={note}
        maxLength={500}
        onChange={(e) => {
          setNote(e.target.value);
        }}
        className="h-[30px] rounded-tile border-0 bg-card px-2.5 text-[13px] inset-shadow-hair"
      />
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={respond.isPending}
          onClick={() => {
            respond.mutate({
              path: ids,
              body: note.trim() === "" ? { reason } : { reason, note },
            });
          }}
        >
          Send
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setAsking(false);
          }}
        >
          Cancel
        </Button>
        {respond.isError && (
          <span className="text-meta text-danger">{errorMessage(respond.error)}</span>
        )}
      </div>
    </fieldset>
  );
}

/** SPEC-042 AC-4: progress, and the client admin's "Mark as done" once everything is done. */
function DoneBar({
  engagementId,
  done,
  total,
  marked,
  canMark,
}: {
  engagementId: string;
  done: number;
  total: number;
  marked: { name: string; at: string } | null;
  canMark: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const mark = useMutation({
    ...markDoneMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(
        clientDoneQueryKey({ path: { engagement_id: engagementId } }),
        data,
      );
    },
  });
  const complete = done >= total;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-pane bg-card px-4 py-3 shadow-e2">
      <div className="flex min-w-[200px] flex-1 flex-col gap-1.5">
        <span className="text-[13px] font-medium">{`${String(done)} of ${String(total)} done`}</span>
        <span className="h-1.5 overflow-hidden rounded-full bg-chip">
          <span
            className="block h-full rounded-full bg-green"
            style={{ width: `${String(Math.round((done / Math.max(total, 1)) * 100))}%` }}
          />
        </span>
      </div>
      {marked !== null ? (
        <span className="text-[12.5px] text-ink-2">
          {`Marked done by ${marked.name || "your team"} on ${longDate(marked.at.slice(0, 10))}`}
        </span>
      ) : (
        canMark && (
          <Button
            variant={complete ? "success" : "tonal"}
            disabled={!complete || mark.isPending}
            onClick={() => {
              mark.mutate({ path: { engagement_id: engagementId } });
            }}
          >
            Mark as done
          </Button>
        )
      )}
      {mark.isError && <span className="text-meta text-danger">{errorMessage(mark.error)}</span>}
    </div>
  );
}
