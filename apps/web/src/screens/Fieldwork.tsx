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
  Button,
  Label,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

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
  picked: "Picked by the team",
};

const VERDICTS: Record<string, string> = {
  explained: "AI: the support explains it",
  not_explained: "AI: the support doesn't explain it",
  unclear: "AI: unclear",
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
  ready: "Ready for review",
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
          <span className="text-sm">{RESULTS[item.result ?? ""] ?? "No result"}</span>
        )}
      </Td>
    </tr>
  );
}

function WorkpaperPanel({
  engagementId,
  procedureId,
  canRun,
  canReview,
}: {
  engagementId: string;
  procedureId: string;
  canRun: boolean;
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
          {canRun && (
            <Button
              size="sm"
              disabled={ready.isPending || w.status === "ready" || w.status === "reviewed"}
              onClick={() => {
                ready.mutate(path);
              }}
            >
              Sign as ready
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
              Sign as reviewed
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
  const canRun = ["engagement_partner", "manager", "senior", "staff"].includes(role ?? "");
  const canReview = ["engagement_partner", "manager", "senior", "reviewer"].includes(role ?? "");
  const choices = (evidence.data ?? []).map((v) => ({
    id: v.id,
    label: `${v.source} v${String(v.version_no)}`,
  }));
  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="Journal entry testing"
        action={
          canRun ? (
            <Button
              size="sm"
              disabled={p.status === "selecting" || select.isPending}
              onClick={() => {
                select.mutate(path);
              }}
            >
              {p.selection ? "Select again" : "Select entries"}
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
              {`${p.population.entry_count.toLocaleString()} journal entries (${p.population.line_count.toLocaleString()} ledger lines) `}
              {p.population.tied
                ? "agree to the general ledger."
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
            <p className="text-muted">No entries selected yet.</p>
          )}
          <p className="text-xs text-muted">
            Not performed: entries posted after year end (needs the subsequent-period ledger) and
            who entered each entry (not in the export).
          </p>
          {select.isError && <Alert title="Couldn't select">{said(select.error)}</Alert>}
        </div>
      </Panel>
      {p.selection != null && (
        <Panel
          title="Selected entries"
          action={
            canRun ? (
              <Button
                size="sm"
                variant="outline"
                disabled={assess.isPending}
                onClick={() => {
                  assess.mutate({ ...path, body: {} });
                }}
              >
                Assess with AI
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
  return (
    <div className="flex flex-col gap-4">
      <MaterialityPanel engagementId={engagementId} canSet={canSet} />
      {jet ? (
        <ProcedurePanel engagementId={engagementId} procedure={jet} role={role} />
      ) : (
        <Panel title="Journal entry testing">
          <div className="flex flex-col gap-2 text-sm">
            <p className="text-muted">
              Selects journal entries from the general ledger by risk criteria and a random sample,
              for your team to test and sign off.
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
    </div>
  );
}
