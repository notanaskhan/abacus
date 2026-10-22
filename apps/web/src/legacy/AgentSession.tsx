import type {
  AssessmentOut,
  FlowOut,
  ItemOut,
  ProcedureOut,
  SessionOut,
} from "@abacus/api-client";
import {
  adoptMutation,
  approvePlanMutation,
  assessMutation,
  assessmentsQueryKey,
  flowQueryKey,
  itemsQueryKey,
  procedureQueryKey,
  proceduresQueryKey,
  requestSelectionSupportMutation,
  sessionOptions,
  sessionQueryKey,
  workpaperQueryKey,
} from "@abacus/api-client/query";
import { Atom, Button, Spinner, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { errorMessage } from "../api";

// SPEC-044 (TASK-109): the agent procedure session. The agent's messages are code's words
// (ADR-111); every gate is a person's click (ADR-005); the agent's judgment is the entry
// assessor's, with citations code verified (ADR-050, ADR-052).

const NAMES: Record<string, string> = {
  journal_entry_testing: "journal entry testing",
  unrecorded_liabilities: "the search for unrecorded liabilities",
};

const SAID: Record<string, string> = {
  ai_assessor_unavailable:
    "The agent can't read documents here yet (no model is switched on). Test the items yourself below.",
  sample_not_approved: "The sample needs a manager's or the partner's approval first.",
  already_requested: "Every item already has a support request.",
  materiality_missing: "Set materiality first.",
  no_ledger: "Import the general ledger for this year first.",
};

function said(error: unknown): string {
  return SAID[errorMessage(error)] ?? "That didn't work. Try again.";
}

function Message({
  children,
  action,
  done = false,
}: {
  children: ReactNode;
  action?: ReactNode;
  done?: boolean;
}): JSX.Element {
  return (
    <li className={`flex gap-2.5 ${done ? "opacity-70" : ""}`}>
      <span
        aria-hidden="true"
        className="mt-0.5 flex size-[22px] shrink-0 items-center justify-center rounded-[6px] bg-espresso text-on-dark"
      >
        <Atom className="size-3" strokeWidth={1.8} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2 rounded-nested bg-card px-3 py-2.5 text-[13px] leading-[1.5] shadow-e1">
        {children}
        {action !== undefined && <div className="flex flex-wrap items-center gap-2">{action}</div>}
      </div>
    </li>
  );
}

export function AgentSession({
  engagementId,
  procedure,
  flow,
  items,
  assessments,
  role,
}: {
  engagementId: string;
  procedure: ProcedureOut;
  flow: FlowOut | undefined;
  items: ItemOut[];
  assessments: AssessmentOut[];
  role: string | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, procedure_id: procedure.id } };
  const session = useQuery({ ...sessionOptions(path), retry: false });
  const refresh = (): void => {
    for (const key of [
      sessionQueryKey(path),
      flowQueryKey(path),
      procedureQueryKey(path),
      itemsQueryKey({ ...path, query: { limit: 500 } }),
      assessmentsQueryKey(path),
      workpaperQueryKey(path),
      proceduresQueryKey({ path: { engagement_id: engagementId } }),
    ]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  };
  const proceed = useMutation({ ...approvePlanMutation(), onSuccess: refresh });
  const ask = useMutation({ ...requestSelectionSupportMutation(), onSuccess: refresh });
  const assess = useMutation({
    ...assessMutation(),
    onSuccess: (data) => {
      toast.show(`The agent is reading the support for ${String(data.items.length)} items`);
      setTimeout(refresh, 5000);
    },
  });
  const adopt = useMutation({
    ...adoptMutation(),
    onSuccess: (data) => {
      toast.show(`${String(data.adopted)} results adopted`);
      refresh();
    },
  });
  const s: SessionOut | undefined = session.data;
  const name = NAMES[procedure.definition] ?? "this procedure";
  const canRun = ["engagement_partner", "manager", "senior", "staff"].includes(role ?? "");
  const canApprove = role === "engagement_partner" || role === "manager";
  const selected = procedure.selection != null;
  const approved = flow?.approval != null;
  const n = items.length;
  const requested = items.filter((i) => i.support_requested).length;
  const byVerdict = (v: string): number => assessments.filter((a) => a.verdict === v).length;
  const assessed = new Set(assessments.map((a) => a.selected_item_id));
  const adoptable = items.filter(
    (i) =>
      i.id != null &&
      i.result == null &&
      assessments.some(
        (a) =>
          a.selected_item_id === i.id &&
          (a.verdict === "explained" || a.verdict === "not_explained"),
      ),
  ).length;
  const withResult = items.filter((i) => i.result != null).length;
  const prepared = (flow?.rows ?? []).filter(
    (r) => r.prepared != null && !r.prepared.stale,
  ).length;
  const reviewed = (flow?.rows ?? []).filter(
    (r) => r.reviewed != null && !r.reviewed.stale,
  ).length;
  const errors = [proceed, ask, assess, adopt].find((m) => m.isError);

  return (
    <section aria-label={`Agent session for ${name}`} className="flex flex-col gap-2">
      <ol className="flex flex-col gap-2">
        {/* AC-1, AC-2: the plan, and the person's approval. */}
        <Message
          done={s?.approved_at != null}
          action={
            s?.approved_at == null && canRun ? (
              <Button
                size="sm"
                disabled={proceed.isPending}
                onClick={() => {
                  proceed.mutate(path);
                }}
              >
                Proceed with plan
              </Button>
            ) : undefined
          }
        >
          <p>{`I drafted a plan for ${name}, in ${String(s?.plan.length ?? 8)} steps:`}</p>
          <ol className="list-decimal pl-5 text-ink-2">
            {(s?.plan ?? []).map((step) => (
              <li key={step.key}>{step.text}</li>
            ))}
          </ol>
          {s?.approved_at != null && (
            <p className="text-[12px] text-ink-3">{`Plan approved by ${s.approved_by_name ?? "your team"}.`}</p>
          )}
        </Message>
        {s?.approved_at != null && procedure.status === "selecting" && (
          <Message>
            <Spinner label="Building the population and selecting…" />
          </Message>
        )}
        {selected && (
          <Message done={approved}>
            <p>
              {`I selected ${String(procedure.selection?.item_count ?? n)} items, from a population that ${procedure.population?.tied === true ? "ties to the ledger" : "didn't tie"}.`}
            </p>
            <p className="text-ink-2">
              {approved
                ? "The sample is approved."
                : canApprove
                  ? "Check the selection below, then approve it there."
                  : "Waiting for a manager or the engagement partner to approve the sample, below."}
            </p>
          </Message>
        )}
        {approved && (
          <Message
            done={requested >= n && n > 0}
            action={
              requested < n && canRun ? (
                <Button
                  size="sm"
                  disabled={ask.isPending}
                  onClick={() => {
                    toast.deferred(`Request for ${String(n - requested)} items sent`, () => {
                      ask.mutate(path);
                    });
                  }}
                >
                  Send the request
                </Button>
              ) : undefined
            }
          >
            <p>
              {requested >= n && n > 0
                ? `The client has one request for the support of all ${String(n)} items.`
                : `Ready to ask the client for the support of ${String(n - requested)} items, in one request, in your firm's words.`}
            </p>
          </Message>
        )}
        {approved && requested > 0 && (
          <Message
            done={assessed.size > 0 && assessed.size >= n}
            action={
              canRun ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={assess.isPending}
                  onClick={() => {
                    assess.mutate({ ...path, body: {} });
                  }}
                >
                  Read the support
                </Button>
              ) : undefined
            }
          >
            <p>
              {assessments.length === 0
                ? "When the client's documents arrive, I'll read each item's support and say whether it explains the entry, citing where."
                : `I read the support for ${String(assessments.length)} items: ${String(byVerdict("explained"))} explained, ${String(byVerdict("not_explained"))} not explained, ${String(byVerdict("unclear"))} unclear.`}
            </p>
          </Message>
        )}
        {adoptable > 0 && (
          <Message
            action={
              canRun ? (
                <Button
                  size="sm"
                  disabled={adopt.isPending}
                  onClick={() => {
                    adopt.mutate({ ...path, body: {} });
                  }}
                >
                  {`Adopt ${String(adoptable)} results`}
                </Button>
              ) : undefined
            }
          >
            <p>
              {`Adopt my proposals as results for ${String(adoptable)} items? Explained becomes supported; not explained becomes an exception with my reason. Unclear items stay for you.`}
            </p>
          </Message>
        )}
        {withResult > 0 && flow !== undefined && (
          <Message done={reviewed >= n && n > 0}>
            <p>
              {`${String(flow.exceptions)} exceptions, ${String(flow.needs_input)} need input, ${String(flow.passed)} passed. Rows prepared ${String(prepared)} of ${String(n)}, reviewed ${String(reviewed)} of ${String(n)}.`}
            </p>
            <p className="text-ink-2">
              Sign the rows and the workpaper below. I don&apos;t sign: your team does.
            </p>
          </Message>
        )}
      </ol>
      {errors !== undefined && (
        <p role="alert" className="pl-8 text-[12.5px] text-red-ink">
          {said(errors.error)}
        </p>
      )}
    </section>
  );
}
