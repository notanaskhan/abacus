import type { ClientContactOut, RequestItemOut } from "@abacus/api-client";
import { upload } from "@abacus/api-client";
import {
  assignToClientMutation,
  clientContactsOptions,
  getEngagementOptions,
  listRequestItemsOptions,
  listRequestItemsQueryKey,
  listUploadsOptions,
  listUploadsQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Label, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { accessToken, signIn } from "../auth/session";
import { statusOf } from "./engagementLabels";

// SPEC-020 AC-9: refusals in plain words (the API returns fixed codes).
const UPLOAD_ERRORS: Record<string, string> = {
  upload_too_large: "The file is over 25 MB.",
  upload_type_not_allowed: "Only PDF, Excel, Word, CSV, PNG and JPEG files can be uploaded.",
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

function size(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${String(Math.max(1, Math.round(bytes / 1024)))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** SPEC-020 AC-1: a client's view of one engagement — its requests by area, with uploads. */
export function ClientEngagement({ engagementId }: { engagementId: string }): JSX.Element {
  const signedIn = accessToken() !== null;
  useEffect(() => {
    if (!signedIn) void signIn(`/client/engagements/${engagementId}`);
  }, [signedIn, engagementId]);
  const path = { path: { engagement_id: engagementId } };
  const engagement = useQuery({ ...getEngagementOptions(path), enabled: signedIn });
  const items = useQuery({ ...listRequestItemsOptions(path), enabled: signedIn });
  // Only client admins may read contacts (and assign): a refusal means a contributor.
  const contacts = useQuery({ ...clientContactsOptions(path), retry: false, enabled: signedIn });
  const contributors = (contacts.data ?? []).filter(
    (c) => c.kind === "member" && c.role === "client_contributor",
  );
  const isAdmin = contacts.isSuccess;

  const areas = new Map<string, RequestItemOut[]>();
  for (const item of items.data ?? []) {
    areas.set(item.audit_area, [...(areas.get(item.audit_area) ?? []), item]);
  }

  return (
    <div className="min-h-screen bg-ground">
      <header className="flex items-center justify-between border-b border-line bg-surface px-6 py-3">
        <span className="font-display text-lg font-semibold">Abacus</span>
        <Link to="/client" className="text-sm text-accent hover:underline">
          Your engagements
        </Link>
      </header>
      <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
        {engagement.isPending ? (
          <Skeleton className="h-12" />
        ) : engagement.isError ? (
          <Alert title="Couldn't load this engagement">{errorMessage(engagement.error)}</Alert>
        ) : (
          <div>
            <h1 className="text-3xl">{engagement.data.name}</h1>
            <p className="text-sm text-muted tabular-nums">
              {engagement.data.client_name} · {engagement.data.fiscal_period_start} to{" "}
              {engagement.data.fiscal_period_end}
            </p>
          </div>
        )}
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
              <ul className="flex flex-col divide-y divide-line">
                {list.map((item) => (
                  <ClientItem
                    key={item.id}
                    item={item}
                    contributors={isAdmin ? contributors : null}
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

function ClientItem({
  item,
  contributors,
}: {
  item: RequestItemOut;
  contributors: ClientContactOut[] | null;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<FileState[]>([]);
  const status = statusOf(item.status);
  const takesFiles = ["open", "received", "needs_revision"].includes(item.status);
  const ids = { engagement_id: item.engagement_id, item_id: item.id };
  const uploads = useQuery({ ...listUploadsOptions({ path: ids }), enabled: open });
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
    void queryClient.invalidateQueries({
      queryKey: listRequestItemsQueryKey({ path: { engagement_id: item.engagement_id } }),
    });
  };

  const inputId = `upload-${item.id}`;
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="font-medium whitespace-pre-line">{item.description}</p>
        <StatusPill tone={status.tone}>{status.label}</StatusPill>
      </div>
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
              className="text-sm"
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
          {open ? "Hide uploads" : "Show uploads"}
        </Button>
        {contributors !== null && (
          <span className="ml-auto flex items-center gap-2 text-sm">
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
              className="h-8 rounded-[var(--radius-control)] border border-line bg-surface px-2 text-sm"
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
      {assign.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(assign.error)}
        </p>
      )}
      {files.length > 0 && (
        <ul aria-label="Files being uploaded" className="flex flex-col gap-1 text-sm">
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
          <p className="text-sm text-danger">{errorMessage(uploads.error)}</p>
        ) : uploads.data.length === 0 ? (
          <p className="text-sm text-muted">No files uploaded yet.</p>
        ) : (
          <ul aria-label="Uploaded files" className="flex flex-col gap-1 text-sm">
            {uploads.data.map((u) => (
              <li key={u.evidence_version_id} className="flex flex-wrap gap-x-2 text-muted">
                <span className="text-ink">{u.file_name}</span>
                <span className="tabular-nums">{size(u.size_bytes)}</span>
                <span>
                  {u.uploaded_by_name || "Someone"} · {new Date(u.uploaded_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        ))}
    </li>
  );
}
