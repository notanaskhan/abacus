import { glImport } from "@abacus/api-client";
import {
  accountsOptions,
  accountsQueryKey,
  bandsMutation,
  glImportFormatsOptions,
  latestGlImportOptions,
  latestGlImportQueryKey,
  procedureQueryKey,
  setAccountsMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Label, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-038 (TASK-086, TASK-087): the search for unrecorded liabilities' inputs: the general
// ledger after year end, the confirmed bank and payables accounts, and the timing bands.

const IMPORT_FAILURES: Record<string, string> = {
  period_mismatch:
    "The export doesn't cover the period after year end exactly: a line falls outside it, or a month has no lines.",
  unbalanced: "Debits and credits in the export don't agree.",
  cutoff_invalid: "The cut-off date is 30 to 366 days after year end.",
  unreadable: "The file couldn't be read in that format.",
  unrecognised_format: "The file doesn't look like that system's general ledger export.",
};

export function SubsequentLedger({
  engagementId,
  canUpload,
}: {
  engagementId: string;
  canUpload: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const status = useQuery({
    ...latestGlImportOptions({ ...path, query: { kind: "subsequent" } }),
    retry: false,
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 3000 : false),
  });
  const formats = useQuery({ ...glImportFormatsOptions(path), retry: false });
  const [format, setFormat] = useState("");
  const [cutoff, setCutoff] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const send = async (file: File): Promise<void> => {
    setBusy(true);
    setFailure(null);
    try {
      await glImport({
        ...path,
        query: {
          format: format || (formats.data?.[0]?.id ?? ""),
          kind: "subsequent",
          ...(cutoff ? { cutoff } : {}),
        },
        body: file as never,
        bodySerializer: null,
        headers: { "Content-Type": file.type || "application/octet-stream" },
        throwOnError: true,
      });
      void queryClient.invalidateQueries({
        queryKey: latestGlImportQueryKey({ ...path, query: { kind: "subsequent" } }),
      });
    } catch (error) {
      setFailure(IMPORT_FAILURES[errorMessage(error)] ?? "The upload didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };
  const s = status.data;
  return (
    <Panel
      title="General ledger after year end"
      action={
        s ? (
          <StatusPill
            tone={
              s.status === "reconciled" ? "success" : s.status === "failed" ? "danger" : "info"
            }
          >
            {s.status === "reconciled"
              ? "Checked"
              : s.status === "failed"
                ? "Not accepted"
                : "Checking…"}
          </StatusPill>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-2 text-body">
        <p className="text-muted">
          The general ledger from the day after year end to the cut-off date (usually the fieldwork
          date). Payments in it are what the search tests.
        </p>
        {s?.status === "reconciled" && (
          <p>{`${(s.line_count ?? 0).toLocaleString()} ledger lines checked.`}</p>
        )}
        {s?.status === "failed" && (
          <Alert title="Not accepted">
            {IMPORT_FAILURES[s.failure_code ?? ""] ?? "The export couldn't be accepted."}
          </Alert>
        )}
        {canUpload && (
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="sub-format">System</Label>
              <select
                id="sub-format"
                value={format}
                onChange={(e) => {
                  setFormat(e.target.value);
                }}
                className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
              >
                {(formats.data ?? []).map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.system}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="sub-cutoff">Cut-off date</Label>
              <input
                id="sub-cutoff"
                type="date"
                value={cutoff}
                onChange={(e) => {
                  setCutoff(e.target.value);
                }}
                className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
              />
            </div>
            <label className="flex flex-col gap-1">
              <span className="font-medium">Export file</span>
              <input
                type="file"
                disabled={busy}
                aria-label="Upload the general ledger after year end"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void send(file);
                }}
              />
            </label>
          </div>
        )}
        {failure !== null && <Alert title="Couldn't upload">{failure}</Alert>}
      </div>
    </Panel>
  );
}

export function Accounts({
  engagementId,
  canSet,
}: {
  engagementId: string;
  canSet: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const current = useQuery({ ...accountsOptions(path), retry: false });
  const [bank, setBank] = useState<string[] | null>(null);
  const [payables, setPayables] = useState<string[] | null>(null);
  const save = useMutation({
    ...setAccountsMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(accountsQueryKey(path), data);
      setBank(null);
      setPayables(null);
    },
  });
  if (current.isPending) return <Skeleton className="h-24" />;
  if (current.isError) {
    return <Alert title="Couldn't load the accounts">{errorMessage(current.error)}</Alert>;
  }
  const a = current.data;
  if (a.accounts.length === 0) {
    return (
      <Panel title="Bank and payables accounts">
        <p className="text-body text-muted">Import the year's general ledger first.</p>
      </Panel>
    );
  }
  const chosenBank = bank ?? (a.confirmed ? a.bank : a.suggested_bank);
  const chosenPayables = payables ?? (a.confirmed ? a.payables : a.suggested_payables);
  const toggle = (list: string[], code: string): string[] =>
    list.includes(code) ? list.filter((c) => c !== code) : [...list, code];
  return (
    <Panel
      title="Bank and payables accounts"
      action={
        <StatusPill tone={a.confirmed ? "success" : "warning"}>
          {a.confirmed ? "Confirmed" : "To confirm"}
        </StatusPill>
      }
    >
      <div className="flex flex-col gap-2 text-body">
        <p className="text-muted">
          Payments are credits to the bank accounts. A bill recorded at year end is a credit to the
          payables account. Suggested from account names: check them.
        </p>
        <div className="grid max-h-64 gap-1 overflow-y-auto sm:grid-cols-[1fr_auto_auto]">
          <span className="font-medium">Account</span>
          <span className="font-medium">Bank</span>
          <span className="font-medium">Payables</span>
          {a.accounts.map((acc) => (
            <div key={acc.code} className="contents">
              <span>{`${acc.code} ${acc.name}`}</span>
              <input
                type="checkbox"
                aria-label={`${acc.code} is a bank account`}
                disabled={!canSet}
                checked={chosenBank.includes(acc.code)}
                onChange={() => {
                  setBank(toggle(chosenBank, acc.code));
                }}
              />
              <input
                type="checkbox"
                aria-label={`${acc.code} is the payables account`}
                disabled={!canSet}
                checked={chosenPayables.includes(acc.code)}
                onChange={() => {
                  setPayables(toggle(chosenPayables, acc.code));
                }}
              />
            </div>
          ))}
        </div>
        {canSet && (
          <div>
            <Button
              size="sm"
              disabled={chosenBank.length === 0 || chosenPayables.length === 0 || save.isPending}
              onClick={() => {
                save.mutate({ ...path, body: { bank: chosenBank, payables: chosenPayables } });
              }}
            >
              {a.confirmed ? "Save changes" : "Confirm accounts"}
            </Button>
          </div>
        )}
        {save.isError && <Alert title="Couldn't save">That didn't work. Try again.</Alert>}
      </div>
    </Panel>
  );
}

interface BandRow {
  until_day: number | null;
  percent: number;
}

export function Bands({
  engagementId,
  procedureId,
  bands,
  thresholds,
  canSet,
}: {
  engagementId: string;
  procedureId: string;
  bands: BandRow[];
  thresholds: string[];
  canSet: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, procedure_id: procedureId } };
  const [edited, setEdited] = useState<BandRow[] | null>(null);
  const save = useMutation({
    ...bandsMutation(),
    onSuccess: () => {
      setEdited(null);
      void queryClient.invalidateQueries({ queryKey: procedureQueryKey(path) });
    },
  });
  const shown = edited ?? bands;
  let start = 1;
  return (
    <Panel title="Timing bands">
      <div className="flex flex-col gap-2 text-body">
        <p className="text-muted">
          A payment is selected when it's at or above its band's threshold, a percentage of
          performance materiality.
        </p>
        <ul className="flex flex-col gap-1">
          {shown.map((b, n) => {
            const from = start;
            start = (b.until_day ?? from) + 1;
            return (
              <li key={n} className="flex flex-wrap items-center gap-2">
                <span className="w-48">
                  {b.until_day === null
                    ? `Day ${String(from)} onwards`
                    : `Days ${String(from)} to ${String(b.until_day)}`}
                </span>
                <input
                  aria-label={`Band ${String(n + 1)} percent`}
                  inputMode="numeric"
                  disabled={!canSet}
                  value={String(b.percent)}
                  onChange={(e) => {
                    setEdited(
                      shown.map((x, i) =>
                        i === n ? { ...x, percent: Number(e.target.value) || 0 } : x,
                      ),
                    );
                  }}
                  className="w-16 rounded-[var(--radius-control)] border border-line bg-surface p-1"
                />
                <span>% of performance materiality</span>
                {thresholds[n] !== undefined && edited === null && (
                  <span className="text-muted tabular-nums">{`= ${Number(thresholds[n]).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}</span>
                )}
              </li>
            );
          })}
        </ul>
        {canSet && edited !== null && (
          <div>
            <Button
              size="sm"
              disabled={save.isPending}
              onClick={() => {
                save.mutate({ ...path, body: { bands: edited } });
              }}
            >
              Save bands
            </Button>
          </div>
        )}
        {save.isError && <Alert title="Couldn't save">Check the percentages (1 to 100).</Alert>}
      </div>
    </Panel>
  );
}
