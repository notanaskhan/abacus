import { type GlFormatOut, glImport } from "@abacus/api-client";
import {
  glImportFormatsOptions,
  latestGlImportOptions,
  latestGlImportQueryKey,
  listRequestItemsQueryKey,
} from "@abacus/api-client/query";
import { Label, Skeleton } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { glFailureMessage, glStatusMessage } from "./glMessages";

// SPEC-034 AC-1, AC-5, AC-9 (TASK-070): upload the general ledger detail beside the trial
// balance, and see where it stands. Nothing here without the flag or the permission.

const MAX_BYTES = 50 * 1024 * 1024;
const TONES = { info: "text-muted", ok: "text-ok", danger: "text-danger" } as const;

export function GlExport({ engagementId }: { engagementId: string }): JSX.Element | null {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const formats = useQuery({ ...glImportFormatsOptions(path), retry: false });
  const latest = useQuery({
    ...latestGlImportOptions(path),
    retry: false,
    refetchInterval: (query) => (query.state.data?.status === "processing" ? 3000 : false),
  });
  const [chosen, setChosen] = useState<GlFormatOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);

  if (formats.isPending) return <Skeleton className="h-16" />;
  if (formats.isError) return null; // not on for this firm, or not allowed
  const system =
    chosen?.system ??
    formats.data.find((f) => f.id === latest.data?.format)?.system ??
    "your accounting system";

  const send = async (file: File): Promise<void> => {
    if (chosen === null) return;
    setRefused(null);
    if (file.size > MAX_BYTES) {
      setRefused("The file is over 50 MB. Your auditor can help with a ledger this large.");
      return;
    }
    setBusy(true);
    try {
      await glImport({
        ...path,
        query: { format: chosen.id },
        body: file as never,
        bodySerializer: null,
        headers: { "Content-Type": file.type || "application/octet-stream" },
        throwOnError: true,
      });
    } catch (error) {
      const code = errorMessage(error);
      setRefused(
        glFailureMessage(
          {
            id: "",
            format: chosen.id,
            status: "failed",
            failure_code: code,
            created_at: "",
          },
          chosen.system,
        ),
      );
    } finally {
      setBusy(false);
      void queryClient.invalidateQueries({ queryKey: latestGlImportQueryKey(path) });
      void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
    }
  };

  const status = latest.data != null ? glStatusMessage(latest.data, system) : null;
  const inputId = `gl-export-${engagementId}`;
  return (
    <section
      aria-label="General ledger detail"
      className="flex flex-col gap-3 border-t border-line pt-3 text-sm"
    >
      <h3 className="font-semibold">General ledger detail</h3>
      <p className="text-muted">
        Every transaction for the year, so your auditor can test them. It&apos;s checked against
        your trial balance.
      </p>
      {status !== null && (
        <p role={status.tone === "danger" ? "alert" : "status"} className={TONES[status.tone]}>
          {status.text}
        </p>
      )}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 font-medium">Which accounting system do you use?</legend>
        <div className="flex flex-wrap gap-2">
          {formats.data.map((f) => (
            <label
              key={f.id}
              className="flex cursor-pointer items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 has-[:checked]:border-stroke has-[:checked]:bg-sel-bg"
            >
              <input
                type="radio"
                name={`gl-system-${engagementId}`}
                value={f.id}
                checked={chosen?.id === f.id}
                onChange={() => {
                  setChosen(f);
                  setRefused(null);
                }}
              />
              {f.system}
            </label>
          ))}
        </div>
      </fieldset>
      {chosen !== null && (
        <>
          <ol className="flex list-decimal flex-col gap-1 pl-5">
            {chosen.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="text-muted">
            {`A ${chosen.file_type.toUpperCase()} file for the whole fiscal year, up to 50 MB.`}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Label htmlFor={inputId}>Upload the general ledger</Label>
            <input
              id={inputId}
              type="file"
              accept={chosen.file_type === "xlsx" ? ".xlsx" : ".csv"}
              disabled={busy}
              className="text-sm"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file !== undefined) void send(file);
              }}
            />
            {busy && <span className="text-muted">Uploading…</span>}
          </div>
        </>
      )}
      {refused !== null && (
        <p role="alert" className="text-danger">
          {refused}
        </p>
      )}
    </section>
  );
}
