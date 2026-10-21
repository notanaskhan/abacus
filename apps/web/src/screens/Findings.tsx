import type { FindingOut, SummaryOut } from "@abacus/api-client";
import {
  engagementGraphOptions,
  findingsOptions,
  findingsQueryKey,
  findingsSummaryOptions,
  findingsSummaryQueryKey,
  meOptions,
  misstatementMutation,
  raiseFindingMutation,
  teamOptions,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  Button,
  type Column,
  DataTable,
  Drawer,
  EmptyState,
  Fieldset,
  Sheet,
  Skeleton,
  StatusPill,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { UncorrectedSummary } from "./Uncorrected";
import { Adjustments, DeficiencyFieldset, Representations, SeverityBadge } from "./Completion";

// SPEC-043 (TASK-107): the findings register and the summary of uncorrected misstatements.
// Code totals; people judge (ADR-050, ADR-005).

const KIND: Record<string, string> = {
  factual: "Factual",
  judgmental: "Judgmental",
  projected: "Projected",
};

const POSITION: Record<
  string,
  { label: string; tone: "success" | "warning" | "danger" | "neutral" }
> = {
  below_performance: { label: "Below performance materiality", tone: "success" },
  at_or_above_performance: { label: "At or above performance materiality", tone: "warning" },
  at_or_above_overall: { label: "At or above overall materiality", tone: "danger" },
  unknown: { label: "Set materiality first", tone: "neutral" },
};

function money(value: string | number): string {
  const n = Number(value);
  const text = Math.abs(n).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return n < 0 ? `(${text})` : text;
}

const RAISERS = new Set(["engagement_partner", "manager", "senior", "staff"]);
const RECORDERS = new Set(["engagement_partner", "manager", "senior"]);

export function Findings({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const findings = useQuery({ ...findingsOptions(path), retry: false });
  const summary = useQuery({ ...findingsSummaryOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role;
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [view, setView] = useState<"findings" | "entries" | "representations">("findings");
  if (findings.isPending) return <Skeleton className="h-40" />;
  if (findings.isError) {
    return (
      <Alert title="Findings aren't available">
        {errorMessage(findings.error) === "forbidden"
          ? "Findings are for the engagement team."
          : errorMessage(findings.error)}
      </Alert>
    );
  }
  const rows = findings.data;
  const viewing = rows.find((f) => f.id === open);
  const columns: Column<FindingOut>[] = [
    {
      key: "title",
      header: "Finding",
      cell: (f) => (
        <span className="flex flex-col">
          <span className="font-medium">{f.title}</span>
          <span className="text-[11.5px] text-ink-3">
            {f.item_id != null ? "From a fieldwork exception" : "Raised by hand"}
            {` · ${f.raised_by_name || "the team"}`}
          </span>
        </span>
      ),
      sortValue: (f) => f.title,
    },
    {
      key: "severity",
      header: "Severity",
      cell: (f) => <SeverityBadge finding={f} />,
    },
    {
      key: "kind",
      header: "Misstatement",
      cell: (f) =>
        f.misstatement == null ? (
          <span className="text-ink-3">Not recorded</span>
        ) : (
          <span>{KIND[f.misstatement.kind] ?? f.misstatement.kind}</span>
        ),
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      cell: (f) =>
        f.misstatement == null ? (
          <span className="text-ink-4">—</span>
        ) : (
          <span className={Number(f.misstatement.amount) < 0 ? "text-red" : ""}>
            {money(f.misstatement.amount)}
          </span>
        ),
      sortValue: (f) => (f.misstatement == null ? null : Math.abs(Number(f.misstatement.amount))),
    },
    {
      key: "corrected",
      header: "Status",
      cell: (f) =>
        f.misstatement == null ? null : f.misstatement.corrected ? (
          <StatusPill tone="success">Corrected</StatusPill>
        ) : (
          <StatusPill tone="warning">Uncorrected</StatusPill>
        ),
    },
  ];
  const views = [
    ["findings", "Findings"],
    ["entries", "Proposed entries"],
    ["representations", "Representations"],
  ] as const;
  const switcher = (
    <div
      role="group"
      aria-label="Completion views"
      className="flex gap-1 self-start rounded-tile bg-nested p-0.5"
    >
      {views.map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={view === key}
          onClick={() => {
            setView(key);
          }}
          className={`rounded-[var(--radius-control)] px-3 py-1 text-[12.5px] ${view === key ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
  if (view === "entries")
    return (
      <div className="flex flex-col gap-3">
        {switcher}
        <Adjustments engagementId={engagementId} role={role ?? ""} findings={rows} />
        <UncorrectedSummary engagementId={engagementId} />
      </div>
    );
  if (view === "representations")
    return (
      <div className="flex flex-col gap-3">
        {switcher}
        <Representations engagementId={engagementId} role={role ?? ""} />
      </div>
    );
  return (
    <div className="flex flex-col gap-3">
      {switcher}
      <SummaryCard summary={summary.data} />
      <section
        aria-labelledby="findings-heading"
        className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
          <h2 id="findings-heading" className="text-[15px] font-medium tracking-[-0.012em]">
            Findings
          </h2>
          <span className="text-[12.5px] text-ink-3 tabular-nums">{rows.length}</span>
          <span className="flex-1" />
          {RAISERS.has(role ?? "") && (
            <Button
              size="sm"
              onClick={() => {
                setCreating(true);
              }}
            >
              New finding
            </Button>
          )}
        </div>
        {rows.length === 0 ? (
          <EmptyState title="No findings yet">
            Raise one from a fieldwork exception, or by hand.
          </EmptyState>
        ) : (
          <DataTable
            label="Findings register"
            rows={rows}
            columns={columns}
            rowKey={(f) => f.id}
            onRowClick={(f) => {
              setOpen(f.id);
            }}
          />
        )}
      </section>
      {creating && (
        <NewFinding
          engagementId={engagementId}
          onClose={() => {
            setCreating(false);
          }}
        />
      )}
      {viewing !== undefined && (
        <FindingDrawer
          engagementId={engagementId}
          finding={viewing}
          canRecord={RECORDERS.has(role ?? "")}
          role={role ?? ""}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
    </div>
  );
}

function SummaryCard({ summary }: { summary: SummaryOut | undefined }): JSX.Element | null {
  if (summary === undefined) return null;
  const position = POSITION[summary.position] ?? POSITION.unknown;
  return (
    <section
      aria-labelledby="sum-heading"
      className="flex flex-col gap-3 rounded-pane bg-card p-4 shadow-e2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="sum-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Uncorrected misstatements
        </h2>
        {position !== undefined && <StatusPill tone={position.tone}>{position.label}</StatusPill>}
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {summary.by_kind.map((k) => (
          <div key={k.kind} className="rounded-nested bg-shell px-3 py-2.5">
            <dt className="text-[11.5px] text-ink-3">{`${KIND[k.kind] ?? k.kind} (${String(k.count)})`}</dt>
            <dd className="text-[15px] font-medium tabular-nums">{money(k.total)}</dd>
          </div>
        ))}
        <div className="rounded-nested bg-sel-bg px-3 py-2.5">
          <dt className="text-[11.5px] text-ink-3">Total</dt>
          <dd className="text-[15px] font-medium tabular-nums">{money(summary.total)}</dd>
        </div>
      </dl>
      {summary.materiality_set && (
        <p className="text-[12px] text-ink-3 tabular-nums">
          {`Overall ${money(summary.overall ?? 0)} · performance ${money(summary.performance ?? 0)} · clearly trivial ${money(summary.trivial ?? 0)} (misstatements at or below it are left out)`}
        </p>
      )}
    </section>
  );
}

function NewFinding({
  engagementId,
  onClose,
}: {
  engagementId: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const raise = useMutation({
    ...raiseFindingMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(findingsQueryKey(path), data);
      toast.show("Finding raised");
      onClose();
    },
  });
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title="New finding"
      footer={
        <Button
          disabled={title.trim() === "" || raise.isPending}
          onClick={() => {
            raise.mutate({
              ...path,
              body: description.trim() === "" ? { title } : { title, description },
            });
          }}
        >
          Raise finding
        </Button>
      }
    >
      <Fieldset title="Finding">
        <input
          aria-label="Title"
          value={title}
          maxLength={200}
          placeholder="What was found"
          onChange={(e) => {
            setTitle(e.target.value);
          }}
          className="mb-2 h-[30px] w-full rounded-tile border-0 bg-nested px-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
        <textarea
          aria-label="Description"
          value={description}
          maxLength={2000}
          placeholder="Details (optional)"
          onChange={(e) => {
            setDescription(e.target.value);
          }}
          className="min-h-[80px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
      </Fieldset>
      {raise.isError && <p className="text-meta text-danger">{errorMessage(raise.error)}</p>}
    </Sheet>
  );
}

function FindingDrawer({
  engagementId,
  finding,
  canRecord,
  role,
  onClose,
}: {
  engagementId: string;
  finding: FindingOut;
  canRecord: boolean;
  role: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const graph = useQuery({ ...engagementGraphOptions(path), retry: false });
  const m = finding.misstatement;
  const [kind, setKind] = useState<"factual" | "judgmental" | "projected">(m?.kind ?? "factual");
  const [amount, setAmount] = useState(m?.amount ?? "");
  const [account, setAccount] = useState(m?.account_code ?? "");
  const [corrected, setCorrected] = useState(m?.corrected ?? false);
  const save = useMutation({
    ...misstatementMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(findingsQueryKey(path), data);
      void queryClient.invalidateQueries({ queryKey: findingsSummaryQueryKey(path) });
      toast.show("Misstatement recorded");
    },
  });
  const g = graph.data;
  const seen = new Map<string, string>();
  for (const a of [
    ...(g?.areas.flatMap((x) => x.accounts) ?? []),
    ...(g?.gaps.unmapped_accounts ?? []),
  ])
    seen.set(a.code, a.name);
  const accounts = [...seen]
    .map(([code, name]) => ({ code, name }))
    .sort((a, b) => a.code.localeCompare(b.code));
  const valid = amount.trim() !== "" && Number(amount) !== 0 && Number.isFinite(Number(amount));
  return (
    <Drawer
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={finding.title}
      meta={
        m == null ? (
          <Badge tone="neutral">No misstatement</Badge>
        ) : (
          <Badge tone={m.corrected ? "success" : "warning"}>
            {m.corrected ? "Corrected" : "Uncorrected"}
          </Badge>
        )
      }
    >
      <Fieldset title="Details">
        <p className="text-[13px] leading-[1.5] whitespace-pre-line">
          {finding.description ?? "No description."}
        </p>
        <p className="mt-2 text-[11.5px] text-ink-3">
          {`Raised by ${finding.raised_by_name || "the team"} on ${new Date(finding.raised_at).toLocaleDateString()}`}
        </p>
      </Fieldset>
      <Fieldset title="Misstatement">
        {m != null && (
          <p className="mb-2 text-[12px] text-ink-3">
            {`Last recorded by ${m.recorded_by_name || "the team"} on ${new Date(m.recorded_at).toLocaleDateString()}`}
          </p>
        )}
        {canRecord ? (
          <div className="flex flex-col gap-2 text-[13px]">
            <label className="flex items-center justify-between gap-3">
              Kind
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as "factual" | "judgmental" | "projected");
                }}
                className="h-[30px] rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
              >
                {Object.entries(KIND).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center justify-between gap-3">
              Amount (overstatement +, understatement −)
              <input
                inputMode="decimal"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                }}
                className="h-[30px] w-[160px] rounded-tile border-0 bg-nested px-2.5 text-right tabular-nums inset-shadow-hair"
              />
            </label>
            <label className="flex items-center justify-between gap-3">
              Account
              {accounts.length > 0 ? (
                <select
                  value={account}
                  onChange={(e) => {
                    setAccount(e.target.value);
                  }}
                  className="h-[30px] max-w-[220px] rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
                >
                  <option value="">Not set</option>
                  {accounts.map((a) => (
                    <option key={a.code} value={a.code}>
                      {`${a.code} ${a.name}`}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={account}
                  maxLength={64}
                  onChange={(e) => {
                    setAccount(e.target.value);
                  }}
                  className="h-[30px] w-[160px] rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair"
                />
              )}
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={corrected}
                onChange={(e) => {
                  setCorrected(e.target.checked);
                }}
              />
              The client has corrected it
            </label>
            <div className="flex items-center justify-end gap-2">
              {save.isError && (
                <span className="text-meta text-danger">{errorMessage(save.error)}</span>
              )}
              <Button
                size="sm"
                disabled={!valid || save.isPending}
                onClick={() => {
                  save.mutate({
                    path: { engagement_id: engagementId, finding_id: finding.id },
                    body: {
                      kind,
                      amount,
                      account_code: account === "" ? null : account,
                      corrected,
                    },
                  });
                }}
              >
                {m == null ? "Record misstatement" : "Save changes"}
              </Button>
            </div>
          </div>
        ) : m == null ? (
          <p className="text-[12.5px] text-ink-2">Not recorded yet.</p>
        ) : (
          <p className="text-[13px] tabular-nums">
            {`${KIND[m.kind] ?? m.kind} · ${money(m.amount)}${m.account_code != null ? ` · ${m.account_code}` : ""}`}
          </p>
        )}
      </Fieldset>
      <DeficiencyFieldset engagementId={engagementId} finding={finding} role={role} />
    </Drawer>
  );
}
