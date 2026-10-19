import type { AssessmentOut, ItemOut, ProcedureOut } from "@abacus/api-client";
import { workpaperFile } from "@abacus/api-client";
import {
  assessMutation,
  assessmentsOptions,
  assessmentsQueryKey,
  conclusionMutation,
  itemsOptions,
  itemsQueryKey,
  listEvidenceVersionsOptions,
  materialityOptions,
  materialityQueryKey,
  meOptions,
  procedureOptions,
  procedureQueryKey,
  proceduresOptions,
  proceduresQueryKey,
  requestSupportMutation,
  resultMutation,
  selectMutation,
  setMaterialityMutation,
  signReadyMutation,
  signReviewedMutation,
  startProcedureMutation,
  teamOptions,
  workpaperOptions,
  workpaperQueryKey,
} from "@abacus/api-client/query";
import {
  AgentText,
  AiTag,
  Alert,
  Badge,
  Button,
  Label,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
  type Tone,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { Accounts, Bands, SubsequentLedger } from "./UnrecordedLiabilities";

// SPEC-037 (TASK-083, TASK-084): journal entry testing. Code builds the population and selects
// entries (ADR-132); people record results, conclude and sign the workpaper (ADR-131).

const MESSAGES: Record<string, string> = {
  fieldwork_unavailable: "Fieldwork isn't switched on for your firm yet.",
  materiality_missing: "Set materiality first.",
  no_ledger: "Import the general ledger for this year first.",
  procedure_exists: "Journal entry testing has already started.",
  procedure_selecting: "Entries are being selected. Try again in a moment.",
  population_not_tied: "The entries didn't agree to the general ledger, so nothing was selected.",
  selection_failed: "Selecting entries failed. Try again.",
  materiality_invalid: "Check the amounts: clearly trivial ≤ performance ≤ overall.",
  result_invalid: "An exception needs a note, and not tested needs a reason.",
  workpaper_incomplete: "Every entry needs a result, and the procedure a conclusion.",
  workpaper_already_signed: "This version is already signed as ready.",
  workpaper_not_ready: "There's no ready version to review.",
  workpaper_changed: "Something changed after it was signed as ready: sign as ready again.",
  reviewer_is_preparer: "The reviewer can't be the person who signed it as ready.",
  workpaper_fingerprint_mismatch: "This version no longer matches what was signed.",
  ai_assessor_unavailable: "AI assessment isn't available here.",
  accounts_missing: "Confirm the bank and payables accounts first.",
  no_subsequent_ledger: "Upload the general ledger after year end first.",
};

const RULES: Record<string, string> = {
  large: "Large",
  round: "Round amount",
  near_year_end: "Near year end",
  manual: "Manual entry",
  rare_account: "Rare account",
  weekend: "Weekend",
  keywords: "Flagged words",
  random: "Random",
  picked: "Unpredictable pick",
  band: "Over its band's threshold",
};

const RELATES: Record<string, string> = { yes: "Yes", no: "No", unclear: "Unclear" };

const VERDICTS: Record<string, string> = {
  explained: "Agent suggests: the support explains it",
  not_explained: "Agent suggests: the support doesn't explain it",
  unclear: "Agent suggests: unclear",
};

// SPEC-037 Q4 (TASK-085): the assessor's proposal, AI-tagged; the team still records the result.
function Assessment({ assessment }: { assessment: AssessmentOut }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1 rounded-[var(--radius-control)] border border-ai-line p-2 text-xs">
      <span className="flex items-center gap-2">
        <AiTag />
        <span className="font-medium">{VERDICTS[assessment.verdict] ?? assessment.verdict}</span>
        <button
          type="button"
          className="text-muted underline"
          onClick={() => {
            setOpen(!open);
          }}
        >
          {open ? "Hide why" : "Why"}
        </button>
      </span>
      {open && (
        <>
          <AgentText text={assessment.rationale} />
          <ul className="flex flex-col gap-1">
            {assessment.citations.map((c, n) => (
              <li key={n} className={c.verified ? "" : "text-muted line-through"}>
                {`${c.document} ${c.page != null ? `p.${String(c.page)}` : `${c.sheet ?? ""} ${c.cell ?? ""}`} (${c.claim}): `}
                <AgentText text={c.quote} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

const STATUS: Record<string, string> = {
  not_started: "Not started",
  draft: "Draft",
  ready: "Prepared",
  reviewed: "Reviewed",
};

const RESULTS: Record<string, string> = {
  supported: "Supported",
  exception: "Exception",
  not_tested: "Not tested",
};

function said(error: unknown): string {
  return MESSAGES[errorMessage(error)] ?? "That didn't work. Try again.";
}

function money(value: string | number): string {
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function useRole(engagementId: string): string | undefined {
  const team = useQuery({
    ...teamOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const me = useQuery(meOptions());
  return team.data?.find((m) => m.user_id === me.data?.user_id)?.role;
}

function MaterialityPanel({
  engagementId,
  canSet,
}: {
  engagementId: string;
  canSet: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const current = useQuery({ ...materialityOptions(path), retry: false });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ overall: "", performance: "", trivial: "", benchmark: "" });
  const save = useMutation({
    ...setMaterialityMutation(),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: materialityQueryKey(path) });
    },
  });
  if (current.isPending) return <Skeleton className="h-24" />;
  if (current.isError)
    return <Alert title="Couldn't load materiality">{said(current.error)}</Alert>;
  const m = current.data;
  const field = (key: keyof typeof form, label: string): JSX.Element => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`mat-${key}`}>{label}</Label>
      <input
        id={`mat-${key}`}
        value={form[key]}
        inputMode={key === "benchmark" ? "text" : "decimal"}
        onChange={(e) => {
          setForm({ ...form, [key]: e.target.value });
        }}
        className="rounded-[var(--radius-control)] border border-line bg-surface p-2 text-sm"
      />
    </div>
  );
  return (
    <Panel
      title="Materiality"
      action={
        canSet && !editing ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setEditing(true);
            }}
          >
            {m ? "Change" : "Set materiality"}
          </Button>
        ) : undefined
      }
    >
      {editing ? (
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {field("overall", "Overall")}
            {field("performance", "Performance")}
            {field("trivial", "Clearly trivial")}
            {field("benchmark", "Benchmark (for example, 1% of revenue)")}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={save.isPending}
              onClick={() => {
                save.mutate({ ...path, body: form });
              }}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
          {save.isError && <Alert title="Couldn't save">{said(save.error)}</Alert>}
        </div>
      ) : m ? (
        <dl className="grid gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-muted">Overall</dt>
            <dd className="tabular-nums">{money(m.overall)}</dd>
          </div>
          <div>
            <dt className="text-muted">Performance</dt>
            <dd className="tabular-nums">{money(m.performance)}</dd>
          </div>
          <div>
            <dt className="text-muted">Clearly trivial</dt>
            <dd className="tabular-nums">{money(m.trivial)}</dd>
          </div>
          <div>
            <dt className="text-muted">Benchmark</dt>
            <dd>{m.benchmark}</dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-muted">
          Not set yet. {canSet ? "" : "The partner or manager sets it."}
        </p>
      )}
    </Panel>
  );
}

function EntryRow({
  engagementId,
  procedureId,
  item,
  evidence,
  canRun,
  assessment,
}: {
  engagementId: string;
  procedureId: string;
  item: ItemOut;
  evidence: { id: string; label: string }[];
  canRun: boolean;
  assessment: AssessmentOut | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [result, setResult] = useState(item.result ?? "");
  const [note, setNote] = useState(item.note ?? "");
  const [linked, setLinked] = useState<string[]>(item.evidence_version_ids ?? []);
  const [relates, setRelates] = useState(item.relates_to_year ?? "");
  const banded = item.band != null;
  const path = { engagement_id: engagementId, procedure_id: procedureId, item_id: item.id ?? "" };
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: itemsQueryKey({
        path: { engagement_id: engagementId, procedure_id: procedureId },
      }),
    });
    void queryClient.invalidateQueries({
      queryKey: workpaperQueryKey({
        path: { engagement_id: engagementId, procedure_id: procedureId },
      }),
    });
  };
  const save = useMutation({ ...resultMutation(), onSuccess: refresh });
  const ask = useMutation({ ...requestSupportMutation(), onSuccess: refresh });
  return (
    <tr>
      <Td className="tabular-nums">{item.posted_on}</Td>
      <Td>
        {item.reference || "—"}
        <div className="text-xs text-muted">{item.kind}</div>
      </Td>
      <Td className="text-right tabular-nums">{money(item.amount)}</Td>
      <Td className="text-xs">
        {item.rules.map((r) => RULES[r] ?? r).join(", ")}
        {item.reason != null && <div className="text-muted">{item.reason}</div>}
        {banded && (
          <div className="text-muted">
            {`Band ${String(item.band)} · `}
            {item.recorded_bill_reference != null
              ? `Bill recorded at year end: ${item.recorded_bill_reference}, ${item.recorded_bill_date ?? ""}`
              : "No matching bill at year end"}
          </div>
        )}
        {assessment !== undefined && <Assessment assessment={assessment} />}
      </Td>
      <Td>
        {canRun ? (
          <div className="flex min-w-[220px] flex-col gap-1 text-sm">
            <select
              aria-label={`Result for ${item.reference || item.posted_on}`}
              value={result}
              onChange={(e) => {
                setResult(e.target.value);
              }}
              className="rounded-[var(--radius-control)] border border-line bg-surface p-1"
            >
              <option value="">No result</option>
              {Object.entries(RESULTS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            {banded && (
              <select
                aria-label={`Relates to the year for ${item.reference || item.posted_on}`}
                value={relates}
                onChange={(e) => {
                  setRelates(e.target.value);
                }}
                className="rounded-[var(--radius-control)] border border-line bg-surface p-1"
              >
                <option value="">Relates to the year?</option>
                {Object.entries(RELATES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {`Relates to the year: ${v}`}
                  </option>
                ))}
              </select>
            )}
            {result !== "" && result !== "supported" && (
              <input
                aria-label="Note"
                placeholder={result === "exception" ? "What's wrong" : "Why not tested"}
                value={note}
                maxLength={2000}
                onChange={(e) => {
                  setNote(e.target.value);
                }}
                className="rounded-[var(--radius-control)] border border-line bg-surface p-1"
              />
            )}
            {evidence.length > 0 && (
              <select
                aria-label="Link evidence"
                multiple
                value={linked}
                onChange={(e) => {
                  setLinked(Array.from(e.target.selectedOptions, (o) => o.value));
                }}
                className="rounded-[var(--radius-control)] border border-line bg-surface p-1 text-xs"
              >
                {evidence.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={result === "" || save.isPending}
                onClick={() => {
                  save.mutate({
                    path,
                    body: {
                      result: result as "supported" | "exception" | "not_tested",
                      note: note || null,
                      evidence_version_ids: linked,
                      relates_to_year:
                        relates === "" ? null : (relates as "yes" | "no" | "unclear"),
                    },
                  });
                }}
              >
                Save
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={item.support_requested || ask.isPending}
                onClick={() => {
                  ask.mutate({ path });
                }}
              >
                {item.support_requested ? "Support requested" : "Ask the client for support"}
              </Button>
            </div>
            {(save.isError || ask.isError) && (
              <span className="text-xs text-danger">{said(save.error ?? ask.error)}</span>
            )}
          </div>
        ) : (
          <span className="text-sm">
            {RESULTS[item.result ?? ""] ?? "No result"}
            {item.relates_to_year != null &&
              ` · relates to the year: ${RELATES[item.relates_to_year] ?? ""}`}
          </span>
        )}
      </Td>
    </tr>
  );
}

function WorkpaperPanel({
  engagementId,
  procedureId,
  canRun,
  canPrepare,
  canReview,
}: {
  engagementId: string;
  procedureId: string;
  canRun: boolean;
  canPrepare: boolean;
  canReview: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, procedure_id: procedureId } };
  const state = useQuery({ ...workpaperOptions(path), retry: false });
  const [text, setText] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: workpaperQueryKey(path) });
  };
  const conclude = useMutation({ ...conclusionMutation(), onSuccess: refresh });
  const ready = useMutation({ ...signReadyMutation(), onSuccess: refresh });
  const reviewed = useMutation({ ...signReviewedMutation(), onSuccess: refresh });
  const download = async (version?: number): Promise<void> => {
    setFailure(null);
    try {
      const { data, response } = await workpaperFile({
        ...path,
        query: version === undefined ? {} : { version },
        parseAs: "blob",
        throwOnError: true,
      });
      const header = response.headers.get("Content-Disposition") ?? "";
      const name = /filename="([^"]+)"/.exec(header)?.[1] ?? "workpaper.xlsx";
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFailure(said(error));
    }
  };
  if (state.isPending) return <Skeleton className="h-32" />;
  if (state.isError) return <Alert title="Couldn't load the workpaper">{said(state.error)}</Alert>;
  const w = state.data;
  const conclusion = text ?? w.conclusion;
  const failed = conclude.error ?? ready.error ?? reviewed.error;
  const tone = w.status === "reviewed" ? "success" : w.status === "ready" ? "info" : "neutral";
  return (
    <Panel title="Workpaper" action={<StatusPill tone={tone}>{STATUS[w.status]}</StatusPill>}>
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-muted">
          {`${String(w.with_result)} of ${String(w.entries)} entries have a result; ${String(w.exceptions)} exception(s).`}
        </p>
        <Label htmlFor="conclusion">Conclusion</Label>
        <textarea
          id="conclusion"
          rows={3}
          maxLength={4000}
          value={conclusion}
          disabled={!canRun}
          onChange={(e) => {
            setText(e.target.value);
          }}
          className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
        />
        <div className="flex flex-wrap gap-2">
          {canRun && (
            <Button
              size="sm"
              variant="outline"
              disabled={conclusion.trim() === "" || conclude.isPending}
              onClick={() => {
                conclude.mutate({ ...path, body: { text: conclusion } });
                setText(null);
              }}
            >
              Save conclusion
            </Button>
          )}
          {canPrepare && (
            <Button
              size="sm"
              disabled={ready.isPending || w.status === "ready" || w.status === "reviewed"}
              onClick={() => {
                ready.mutate(path);
              }}
            >
              Sign off as preparer
            </Button>
          )}
          {canReview && (
            <Button
              size="sm"
              disabled={reviewed.isPending || w.status !== "ready"}
              onClick={() => {
                reviewed.mutate(path);
              }}
            >
              Sign off as reviewer
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => void download()}>
            Download draft
          </Button>
        </div>
        {w.versions.length > 0 && (
          <ul aria-label="Signed versions" className="flex flex-col gap-1">
            {w.versions.map((v) => (
              <li key={v.version} className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{`Version ${String(v.version)}`}</span>
                <span className="text-muted">
                  {v.signatures
                    .map((g) => `${g.kind === "ready" ? "Ready" : "Reviewed"}: ${g.name}`)
                    .join(" · ")}
                </span>
                <Button size="sm" variant="ghost" onClick={() => void download(v.version)}>
                  Download
                </Button>
              </li>
            ))}
          </ul>
        )}
        {failed != null && <Alert title="Couldn't do that">{said(failed)}</Alert>}
        {failure != null && <Alert title="Couldn't download">{failure}</Alert>}
      </div>
    </Panel>
  );
}

function ProcedurePanel({
  engagementId,
  procedure,
  role,
}: {
  engagementId: string;
  procedure: ProcedureOut;
  role: string | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, procedure_id: procedure.id } };
  const detail = useQuery({
    ...procedureOptions(path),
    initialData: procedure,
    refetchInterval: (q) => (q.state.data?.status === "selecting" ? 3000 : false),
  });
  const items = useQuery({
    ...itemsOptions({ ...path, query: { limit: 500 } }),
    enabled: detail.data.selection != null,
  });
  const evidence = useQuery({
    ...listEvidenceVersionsOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const assessments = useQuery({
    ...assessmentsOptions(path),
    enabled: detail.data.selection != null,
    retry: false,
  });
  const assess = useMutation({
    ...assessMutation(),
    onSuccess: () => {
      setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: assessmentsQueryKey(path) });
      }, 4000);
    },
  });
  const byItem = new Map((assessments.data ?? []).map((a) => [a.selected_item_id, a]));
  const select = useMutation({
    ...selectMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procedureQueryKey(path) });
    },
  });
  const p = detail.data;
  const surl = p.definition === "unrecorded_liabilities";
  const canSet = role === "engagement_partner" || role === "manager";
  const canRun = ["engagement_partner", "manager", "senior", "staff"].includes(role ?? "");
  // ADR-131 Q2 (TASK-089): staff, senior or manager prepare; senior, manager or partner review,
  // never the EQR (`reviewer`), who signs only at L5
  const canPrepare = ["manager", "senior", "staff"].includes(role ?? "");
  const canReview = ["engagement_partner", "manager", "senior"].includes(role ?? "");
  const choices = (evidence.data ?? []).map((v) => ({
    id: v.id,
    label: `${v.source} v${String(v.version_no)}`,
  }));
  return (
    <div className="flex flex-col gap-3">
      {surl && (
        <div className="grid items-start gap-3 xl:grid-cols-2">
          <SubsequentLedger engagementId={engagementId} canUpload={canRun} />
          <Bands
            engagementId={engagementId}
            procedureId={p.id}
            bands={(p.parameters.bands ?? []) as { until_day: number | null; percent: number }[]}
            thresholds={
              ((p.parameters.thresholds as string[] | undefined) ?? []) satisfies string[]
            }
            canSet={canSet}
          />
        </div>
      )}
      {surl && <Accounts engagementId={engagementId} canSet={canSet} />}
      <Panel
        title="Selection"
        action={
          canRun ? (
            <Button
              size="sm"
              disabled={p.status === "selecting" || select.isPending}
              onClick={() => {
                select.mutate(path);
              }}
            >
              {p.selection ? "Select again" : surl ? "Select payments" : "Select entries"}
            </Button>
          ) : undefined
        }
      >
        <div className="flex flex-col gap-2 text-sm">
          {p.status === "selecting" && <p className="text-muted">Selecting entries…</p>}
          {p.status === "failed" && (
            <Alert title="Selection didn't finish">
              {MESSAGES[p.failure_code ?? ""] ?? "Try again."}
            </Alert>
          )}
          {p.population != null && (
            <p>
              {surl
                ? `${p.population.entry_count.toLocaleString()} payments after year end, ${Number(p.population.total_debit).toLocaleString("en-US", { minimumFractionDigits: 2 })} in total, `
                : `${p.population.entry_count.toLocaleString()} journal entries (${p.population.line_count.toLocaleString()} ledger lines) `}
              {p.population.tied
                ? surl
                  ? "agree to the bank-account credits in the export."
                  : "agree to the general ledger."
                : "didn't agree to the general ledger."}
            </p>
          )}
          {p.selection != null && (
            <p className="text-muted">
              {`${String(p.selection.item_count)} selected: `}
              {Object.entries(p.selection.by_rule)
                .map(([r, n]) => `${RULES[r] ?? r} ${String(n)}`)
                .join(" · ")}
            </p>
          )}
          {p.selection == null && p.status !== "selecting" && (
            <p className="text-muted">
              {surl ? "No payments selected yet." : "No entries selected yet."}
            </p>
          )}
          {!surl && (
            <p className="text-xs text-muted">
              Not performed: entries posted after year end (needs the subsequent-period ledger) and
              who entered each entry (not in the export).
            </p>
          )}
          {select.isError && <Alert title="Couldn't select">{said(select.error)}</Alert>}
        </div>
      </Panel>
      {p.selection != null && (
        <Panel
          title={surl ? "Selected payments" : "Selected entries"}
          action={
            canRun && !surl ? (
              <Button
                size="sm"
                variant="outline"
                disabled={assess.isPending}
                onClick={() => {
                  assess.mutate({ ...path, body: {} });
                }}
              >
                Assess with agent
              </Button>
            ) : undefined
          }
        >
          {assess.isError && <Alert title="Couldn't start">{said(assess.error)}</Alert>}
          {assess.isSuccess && (
            <p className="text-xs text-muted">
              {`Assessing ${String(assess.data.items.length)} entries with linked support. AI proposals appear beside each entry; your team still records every result.`}
            </p>
          )}
          {items.isPending ? (
            <Skeleton className="h-40" />
          ) : items.isError ? (
            <Alert title="Couldn't load the entries">{said(items.error)}</Alert>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[760px]">
                <thead>
                  <tr>
                    <Th>Date</Th>
                    <Th>Entry</Th>
                    <Th className="text-right">Amount</Th>
                    <Th>Why selected</Th>
                    <Th>Result</Th>
                  </tr>
                </thead>
                <tbody>
                  {items.data.map((item) => (
                    <EntryRow
                      key={item.id ?? item.position}
                      engagementId={engagementId}
                      procedureId={p.id}
                      item={item}
                      evidence={choices}
                      canRun={canRun}
                      assessment={item.id != null ? byItem.get(item.id) : undefined}
                    />
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </Panel>
      )}
      {p.selection != null && (
        <WorkpaperPanel
          engagementId={engagementId}
          procedureId={p.id}
          canRun={canRun}
          canPrepare={canPrepare}
          canReview={canReview}
        />
      )}
    </div>
  );
}

export function Fieldwork({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const role = useRole(engagementId);
  const procedures = useQuery({ ...proceduresOptions(path), retry: false });
  const start = useMutation({
    ...startProcedureMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: proceduresQueryKey(path) });
    },
  });
  const canSet = role === "engagement_partner" || role === "manager";
  const canRun = canSet || role === "senior" || role === "staff";
  if (procedures.isPending) return <Skeleton className="h-64" />;
  if (procedures.isError) {
    return (
      <Alert title="Fieldwork isn't available">
        {errorMessage(procedures.error) === "forbidden"
          ? "Fieldwork is for the engagement team."
          : said(procedures.error)}
      </Alert>
    );
  }
  const jet = procedures.data.find((p) => p.definition === "journal_entry_testing");
  const surl = procedures.data.find((p) => p.definition === "unrecorded_liabilities");
  return (
    <div className="grid items-start gap-3 lg:grid-cols-[264px_minmax(0,1fr)]">
      <FieldworkRail engagementId={engagementId} jet={jet} surl={surl} />
      <div className="flex min-w-0 flex-col gap-6">
        <section id="fw-materiality" className="scroll-mt-[58px]">
          <MaterialityPanel engagementId={engagementId} canSet={canSet} />
        </section>
        <section id="fw-jet" aria-label="Journal entry testing" className="scroll-mt-[58px]">
          <SectionHeading title="Journal entry testing" procedure={jet} />
          {jet ? (
            <ProcedurePanel engagementId={engagementId} procedure={jet} role={role} />
          ) : (
            <Panel title="Not started">
              <div className="flex flex-col gap-2 text-sm">
                <p className="text-muted">
                  Selects journal entries from the general ledger by risk criteria and a random
                  sample, for your team to test and sign off.
                </p>
                {canRun && (
                  <div>
                    <Button
                      size="sm"
                      disabled={start.isPending}
                      onClick={() => {
                        start.mutate(path);
                      }}
                    >
                      Start
                    </Button>
                  </div>
                )}
                {start.isError && <Alert title="Couldn't start">{said(start.error)}</Alert>}
              </div>
            </Panel>
          )}
        </section>
        <section
          id="fw-surl"
          aria-label="Search for unrecorded liabilities"
          className="scroll-mt-[58px]"
        >
          <SectionHeading title="Search for unrecorded liabilities" procedure={surl} />
          {surl ? (
            <ProcedurePanel engagementId={engagementId} procedure={surl} role={role} />
          ) : (
            <Panel title="Not started">
              <div className="flex flex-col gap-2 text-sm">
                <p className="text-muted">
                  Tests payments made after year end for liabilities that should have been recorded
                  at year end: larger payments by timing band, with a check for a matching bill.
                </p>
                {canRun && (
                  <div>
                    <Button
                      size="sm"
                      disabled={start.isPending}
                      onClick={() => {
                        start.mutate({ ...path, body: { definition: "unrecorded_liabilities" } });
                      }}
                    >
                      Start
                    </Button>
                  </div>
                )}
              </div>
            </Panel>
          )}
        </section>
      </div>
    </div>
  );
}

/** A procedure's state in a word (TASK-096). */
function procedureState(p: ProcedureOut | undefined): { label: string; tone: Tone } {
  if (p === undefined) return { label: "Not started", tone: "neutral" };
  if (p.status === "selecting") return { label: "Selecting", tone: "warning" };
  if (p.status === "failed") return { label: "Needs attention", tone: "danger" };
  if (p.selection != null)
    return { label: `${String(p.selection.item_count)} selected`, tone: "success" };
  return { label: "Set up", tone: "warning" };
}

function SectionHeading({
  title,
  procedure,
}: {
  title: string;
  procedure: ProcedureOut | undefined;
}): JSX.Element {
  const state = procedureState(procedure);
  return (
    <div className="mb-2.5 flex items-center gap-2.5 px-1">
      <h2 className="text-[15px] font-medium tracking-[-0.012em]">{title}</h2>
      <StatusPill tone={state.tone}>{state.label}</StatusPill>
    </div>
  );
}

/** The cockpit's rail (TASK-096, the plan's T2): materiality and each procedure with its state;
 * a row jumps to its section. */
function FieldworkRail({
  engagementId,
  jet,
  surl,
}: {
  engagementId: string;
  jet: ProcedureOut | undefined;
  surl: ProcedureOut | undefined;
}): JSX.Element {
  const current = useQuery({
    ...materialityOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const m = current.data;
  const rows: { id: string; title: string; meta: string; state: { label: string; tone: Tone } }[] =
    [
      {
        id: "fw-materiality",
        title: "Materiality",
        meta: m == null ? "Not set yet" : `Performance ${money(m.performance)}`,
        state:
          m == null ? { label: "To set", tone: "warning" } : { label: "Set", tone: "success" },
      },
      {
        id: "fw-jet",
        title: "Journal entry testing",
        meta: "Risk criteria and a random sample",
        state: procedureState(jet),
      },
      {
        id: "fw-surl",
        title: "Search for unrecorded liabilities",
        meta: "Payments after year end",
        state: procedureState(surl),
      },
    ];
  return (
    <nav
      aria-label="Procedures"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2 lg:sticky lg:top-[58px]"
    >
      <div className="flex h-[46px] items-center border-b-[0.5px] border-hair px-4 text-[14.5px] font-medium tracking-[-0.012em]">
        Procedures
      </div>
      <ul className="flex flex-col p-1.5">
        {rows.map((r) => (
          <li key={r.id}>
            <a
              href={`#${r.id}`}
              className="flex flex-col gap-1 rounded-tile px-2.5 py-2 text-ink hover:bg-nav-fill hover:no-underline"
            >
              <span className="text-[13px] font-medium">{r.title}</span>
              <span className="flex items-center justify-between gap-2">
                <span className="truncate text-[11.5px] text-ink-3">{r.meta}</span>
                <span className="shrink-0">
                  <Badge tone={r.state.tone}>{r.state.label}</Badge>
                </span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
