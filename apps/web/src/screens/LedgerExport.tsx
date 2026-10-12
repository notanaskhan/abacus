import { type FormatOut, type ImportOut, ledgerImport } from "@abacus/api-client";
import {
  connectionQueryKey,
  getEngagementOptions,
  latestLedgerImportQueryKey,
  ledgerImportFormatsOptions,
  listRequestItemsQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, Label, Skeleton } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { importFailureMessage, longDate } from "./importMessages";

const MAX_BYTES = 20 * 1024 * 1024;

type Outcome = { tone: "success" | "danger"; text: string };

function detailOf(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
  }
  return "";
}

/** The plain-words result of an upload (SPEC-028 §4.8, ADR-111). */
export function importOutcome(result: ImportOut, system: string, periodEnd?: string): Outcome {
  if (result.duplicate) {
    return { tone: "success", text: "You've already uploaded this file. Nothing has changed." };
  }
  if (result.status === "received") {
    return { tone: "success", text: "Received. We're preparing your trial balance." };
  }
  return {
    tone: "danger",
    text: importFailureMessage({
      code: result.failure_code ?? "",
      system,
      difference: result.difference,
      foundPeriodEnd: result.found_period_end,
      periodEnd: periodEnd ?? result.period_end,
    }),
  };
}

/** SPEC-028 AC-2 (TASK-053): pick the accounting system, follow its export steps, upload the
 * file for the engagement's year end, and see at once whether it worked. */
export function LedgerExport({
  engagementId,
  onBehalf,
  onDone,
}: {
  engagementId: string;
  onBehalf: boolean;
  onDone?: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const formats = useQuery({ ...ledgerImportFormatsOptions(path), retry: false });
  const engagement = useQuery(getEngagementOptions(path));
  const [chosen, setChosen] = useState<FormatOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  if (formats.isPending) return <Skeleton className="h-24" />;
  if (formats.isError) {
    return <Alert title="Export isn't available">We couldn't load the export options.</Alert>;
  }
  const periodEnd = engagement.data?.fiscal_period_end;

  const send = async (file: File): Promise<void> => {
    if (chosen === null) return;
    if (file.size > MAX_BYTES) {
      setOutcome({
        tone: "danger",
        text: importFailureMessage({ code: "payload_too_large", system: chosen.system }),
      });
      return;
    }
    setBusy(true);
    setOutcome(null);
    try {
      const { data } = await ledgerImport({
        ...path,
        query: { format: chosen.id },
        body: file as never,
        bodySerializer: null,
        headers: { "Content-Type": file.type || "application/octet-stream" },
        throwOnError: true,
      });
      setOutcome(importOutcome(data, chosen.system, periodEnd));
    } catch (error) {
      setOutcome({
        tone: "danger",
        text: importFailureMessage({ code: detailOf(error), system: chosen.system }),
      });
    } finally {
      setBusy(false);
      void queryClient.invalidateQueries({ queryKey: latestLedgerImportQueryKey(path) });
      void queryClient.invalidateQueries({ queryKey: connectionQueryKey(path) });
      void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
    }
  };

  const inputId = `ledger-export-${engagementId}`;
  return (
    <div className="flex flex-col gap-3 text-sm">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 font-medium">Which accounting system do you use?</legend>
        <div className="flex flex-wrap gap-2">
          {formats.data.map((f) => (
            <label
              key={f.id}
              className="flex cursor-pointer items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 has-[:checked]:border-accent"
            >
              <input
                type="radio"
                name={`system-${engagementId}`}
                value={f.id}
                checked={chosen?.id === f.id}
                onChange={() => {
                  setChosen(f);
                  setOutcome(null);
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
            {periodEnd !== undefined
              ? `The trial balance for the year ending ${longDate(periodEnd)}, as a ${chosen.file_type.toUpperCase()} file.`
              : `A ${chosen.file_type.toUpperCase()} file.`}
            {onBehalf && " You're uploading it for the client."}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Label htmlFor={inputId}>Upload the export</Label>
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
            {busy && <span className="text-muted">Checking the file…</span>}
          </div>
        </>
      )}
      {outcome !== null && (
        <p
          role={outcome.tone === "danger" ? "alert" : "status"}
          className={outcome.tone === "danger" ? "text-danger" : "text-ok"}
        >
          {outcome.text}
        </p>
      )}
      {onDone !== undefined && (
        <div>
          <Button size="sm" variant="ghost" onClick={onDone}>
            Close
          </Button>
        </div>
      )}
    </div>
  );
}
