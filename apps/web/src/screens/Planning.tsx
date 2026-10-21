import type { MaterialityVersionOut, RiskBody, RiskOut } from "@abacus/api-client";
import {
  addRiskMutation,
  approveRiskMutation,
  decideMaterialityMutation,
  materialityQueryKey,
  materialityVersionsOptions,
  materialityVersionsQueryKey,
  meOptions,
  reviseRiskMutation,
  risksOptions,
  risksQueryKey,
  setMaterialityMutation,
  teamOptions,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  Button,
  type Column,
  DataTable,
  EmptyState,
  Fieldset,
  prose,
  Sheet,
  Skeleton,
  StatusPill,
  toast,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-300 (TASK-301): planning. Materiality is proposed by a manager or the partner, computed by
// code from its basis (ADR-050), and decided only by the engagement partner. The risk register:
// code combines inherent and control risk; the partner approves significant risks and rebuttals.

const PROPOSERS = new Set(["engagement_partner", "manager"]);
const ASSESSORS = new Set(["engagement_partner", "manager", "senior"]);

const RATING: Record<string, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  maximum: "Maximum",
};
const RATING_TONE: Record<string, "success" | "warning" | "danger"> = {
  low: "success",
  moderate: "warning",
  high: "danger",
};
const ASSERTION: Record<RiskBody["assertions"][number], string> = {
  existence: "Existence",
  completeness: "Completeness",
  accuracy: "Accuracy",
  valuation: "Valuation",
  cut_off: "Cut-off",
  rights_obligations: "Rights and obligations",
  presentation: "Presentation",
};
const LEVEL: Record<string, string> = {
  financial_statement: "Financial statement",
  assertion: "Assertion",
};

// Materiality reads as whole dollars unless it has cents ($252,200, $1,234.50): a planning figure,
// not a ledger cell, so the plan's two decimals on every cell does not apply (SPEC-300).
function money(value: string | number | null | undefined): string {
  return prose(value ?? 0).replace(/\.00$/, "");
}

function pct(value: string | null | undefined): string {
  return `${String(Number(value ?? 0))}%`;
}

/** Preview only; the server recomputes (SPEC-300 AC-1). Mirrors `planning.compute`. */
export function previewAmounts(
  basis: number,
  rate: number,
  pm: number,
  ct: number,
): { overall: number; performance: number; trivial: number } | null {
  if (!(basis > 0 && rate > 0 && rate <= 100 && pm > 0 && pm <= 100 && ct > 0 && ct <= pm))
    return null;
  const round = (v: number): number => {
    const step = v >= 1000 ? 100 : 1;
    return Math.max(Math.round(v / step) * step, 1);
  };
  const overall = round((basis * rate) / 100);
  const performance = Math.min(round((overall * pm) / 100), overall);
  return { overall, performance, trivial: Math.min(round((overall * ct) / 100), performance) };
}

export function Planning({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? "";
  return (
    <div className="flex flex-col gap-3">
      <MaterialityCard engagementId={engagementId} role={role} />
      <RiskRegister engagementId={engagementId} role={role} />
    </div>
  );
}

function MaterialityCard({
  engagementId,
  role,
}: {
  engagementId: string;
  role: string;
}): JSX.Element {
  const fmt = useFormat();
  const path = { path: { engagement_id: engagementId } };
  const versions = useQuery({ ...materialityVersionsOptions(path), retry: false });
  const [proposing, setProposing] = useState(false);
  const [deciding, setDeciding] = useState(false);
  if (versions.isPending) return <Skeleton className="h-40" />;
  if (versions.isError) {
    return (
      <Alert title="Planning isn't available">
        {errorMessage(versions.error) === "forbidden"
          ? "Planning is for the engagement team."
          : errorMessage(versions.error)}
      </Alert>
    );
  }
  const [current, ...earlier] = versions.data;
  const isPartner = role === "engagement_partner";
  return (
    <section
      aria-labelledby="mat-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="mat-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Materiality
        </h2>
        {current !== undefined && (
          <span className="text-[12.5px] text-ink-3 tabular-nums">{`v${String(current.version)}`}</span>
        )}
        {current !== undefined &&
          (current.status === "decided" ? (
            <StatusPill tone="success">Decided</StatusPill>
          ) : (
            <StatusPill tone="warning">Waiting on the partner</StatusPill>
          ))}
        <span className="flex-1" />
        {isPartner && current?.status === "proposed" && (
          <Button
            size="sm"
            onClick={() => {
              setDeciding(true);
            }}
          >
            Decide materiality
          </Button>
        )}
        {PROPOSERS.has(role) && (
          <Button
            size="sm"
            variant={current?.status === "proposed" && isPartner ? "outline" : "default"}
            onClick={() => {
              setProposing(true);
            }}
          >
            {current === undefined ? "Propose materiality" : "Propose a new version"}
          </Button>
        )}
      </div>
      {current === undefined ? (
        <EmptyState title="No materiality yet">
          {PROPOSERS.has(role)
            ? "Propose it from a benchmark; the engagement partner decides it. Sampling waits for the decision."
            : "A manager or the partner proposes it; the engagement partner decides it."}
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3 p-4">
          <Amounts version={current} />
          {current.status === "proposed" && !isPartner && (
            <p className="text-[12.5px] text-ink-3">
              Sampling waits until the engagement partner decides materiality.
            </p>
          )}
          {current.decision_rationale != null && (
            <p className="text-[12.5px] leading-[1.5]">
              <span className="text-ink-3">
                {`Decided by ${current.decided_by_name ?? "the partner"} on ${fmt.date(current.decided_at)}: `}
              </span>
              {current.decision_rationale}
            </p>
          )}
          {earlier.length > 0 && (
            <details className="text-[12.5px]">
              <summary className="cursor-pointer text-ink-3">{`Earlier versions (${String(earlier.length)})`}</summary>
              <ul className="mt-2 flex flex-col gap-1.5">
                {earlier.map((v) => (
                  <li key={v.id} className="flex gap-2 tabular-nums">
                    <span className="w-8 text-ink-3">{`v${String(v.version)}`}</span>
                    <span>{`${money(v.overall)} overall · ${money(v.performance)} performance`}</span>
                    <span className="text-ink-3">
                      {`${v.decided_at != null ? "Decided" : "Proposed"} · ${v.set_by_name || "the team"} · ${fmt.date(v.set_at)}`}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
      {proposing && (
        <ProposeMateriality
          engagementId={engagementId}
          current={current}
          onClose={() => {
            setProposing(false);
          }}
        />
      )}
      {deciding && current !== undefined && (
        <DecideMateriality
          engagementId={engagementId}
          version={current}
          onClose={() => {
            setDeciding(false);
          }}
        />
      )}
    </section>
  );
}

function Amounts({ version: v }: { version: MaterialityVersionOut }): JSX.Element {
  const fmt = useFormat();
  const proposerWhy = v.rationale; // a person's words, not the agent's
  return (
    <>
      <dl className="grid grid-cols-3 gap-3">
        {[
          ["Overall", v.overall, v.rate_pct != null ? `${pct(v.rate_pct)} of the basis` : null],
          [
            "Performance",
            v.performance,
            v.performance_pct != null ? `${pct(v.performance_pct)} of overall` : null,
          ],
          [
            "Clearly trivial",
            v.trivial,
            v.trivial_pct != null ? `${pct(v.trivial_pct)} of overall` : null,
          ],
        ].map(([label, amount, note]) => (
          <div key={label} className="rounded-nested bg-shell px-3 py-2.5">
            <dt className="text-[11.5px] text-ink-3">{label}</dt>
            <dd className="text-[15px] font-medium tabular-nums">{money(amount)}</dd>
            {note != null && <dd className="text-[11.5px] text-ink-3">{note}</dd>}
          </div>
        ))}
      </dl>
      <p className="text-[12.5px] text-ink-2 tabular-nums">
        {v.basis_amount != null
          ? `Benchmark: ${v.benchmark}, ${money(v.basis_amount)}`
          : `Benchmark: ${v.benchmark}`}
        <span className="text-ink-3">{` · proposed by ${v.set_by_name || "the team"} on ${fmt.date(v.set_at)}`}</span>
      </p>
      {proposerWhy != null && <p className="text-[12.5px] leading-[1.5]">{proposerWhy}</p>}
    </>
  );
}

function ProposeMateriality({
  engagementId,
  current,
  onClose,
}: {
  engagementId: string;
  current: MaterialityVersionOut | undefined;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const [benchmark, setBenchmark] = useState(current?.benchmark ?? "");
  const [basis, setBasis] = useState(current?.basis_amount ?? "");
  const [rate, setRate] = useState(current?.rate_pct ?? "1");
  const [pm, setPm] = useState(current?.performance_pct ?? "75");
  const [ct, setCt] = useState(current?.trivial_pct ?? "5");
  const [rationale, setRationale] = useState("");
  const preview = previewAmounts(Number(basis), Number(rate), Number(pm), Number(ct));
  const save = useMutation({
    ...setMaterialityMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: materialityVersionsQueryKey(path) });
      void queryClient.invalidateQueries({ queryKey: materialityQueryKey(path) });
      toast.show("Materiality proposed");
      onClose();
    },
  });
  const input =
    "h-[30px] w-[140px] rounded-tile border-0 bg-nested px-2.5 text-right tabular-nums inset-shadow-hair";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title="Propose materiality"
      footer={
        <Button
          disabled={preview === null || benchmark.trim() === "" || save.isPending}
          onClick={() => {
            if (preview === null) return;
            save.mutate({
              ...path,
              body: {
                overall: String(preview.overall),
                performance: String(preview.performance),
                trivial: String(preview.trivial),
                benchmark,
                basis: { amount: basis, rate_pct: rate, performance_pct: pm, trivial_pct: ct },
                ...(rationale.trim() === "" ? {} : { rationale }),
              },
            });
          }}
        >
          Propose
        </Button>
      }
    >
      <Fieldset title="Basis">
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Benchmark
            <input
              value={benchmark}
              maxLength={200}
              placeholder="Net assets"
              onChange={(e) => {
                setBenchmark(e.target.value);
              }}
              className="h-[30px] w-[220px] rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair"
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Benchmark amount ($)
            <input
              inputMode="decimal"
              value={basis}
              onChange={(e) => {
                setBasis(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Overall, % of the benchmark
            <input
              inputMode="decimal"
              value={rate}
              onChange={(e) => {
                setRate(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Performance, % of overall
            <input
              inputMode="decimal"
              value={pm}
              onChange={(e) => {
                setPm(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Clearly trivial, % of overall
            <input
              inputMode="decimal"
              value={ct}
              onChange={(e) => {
                setCt(e.target.value);
              }}
              className={input}
            />
          </label>
        </div>
      </Fieldset>
      <Fieldset title="Amounts">
        {preview === null ? (
          <p className="text-[12.5px] text-ink-3">
            Enter a benchmark amount and percentages (clearly trivial ≤ performance).
          </p>
        ) : (
          <dl
            className="grid grid-cols-3 gap-2 text-[13px] tabular-nums"
            aria-label="Computed amounts"
          >
            <div>
              <dt className="text-[11.5px] text-ink-3">Overall</dt>
              <dd>{money(preview.overall)}</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-ink-3">Performance</dt>
              <dd>{money(preview.performance)}</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-ink-3">Clearly trivial</dt>
              <dd>{money(preview.trivial)}</dd>
            </div>
          </dl>
        )}
        <p className="mt-2 text-[11.5px] text-ink-3">Rounded to the nearest hundred dollars.</p>
      </Fieldset>
      <Fieldset title="Why this benchmark">
        <textarea
          aria-label="Rationale"
          value={rationale}
          maxLength={2000}
          placeholder="Users of the statements, qualitative factors (optional)"
          onChange={(e) => {
            setRationale(e.target.value);
          }}
          className="min-h-[80px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
      </Fieldset>
      {save.isError && <p className="text-meta text-danger">{errorMessage(save.error)}</p>}
    </Sheet>
  );
}

function DecideMateriality({
  engagementId,
  version,
  onClose,
}: {
  engagementId: string;
  version: MaterialityVersionOut;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const [rationale, setRationale] = useState("");
  const decide = useMutation({
    ...decideMaterialityMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(materialityVersionsQueryKey(path), data);
      void queryClient.invalidateQueries({ queryKey: materialityQueryKey(path) });
      toast.show("Materiality decided");
      onClose();
    },
  });
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Decide materiality v${String(version.version)}`}
      footer={
        <Button
          disabled={rationale.trim() === "" || decide.isPending}
          onClick={() => {
            decide.mutate({ ...path, body: { rationale } });
          }}
        >
          Decide
        </Button>
      }
    >
      <Fieldset title="Proposed">
        <Amounts version={version} />
      </Fieldset>
      <Fieldset title="Your rationale">
        <textarea
          aria-label="Decision rationale"
          value={rationale}
          maxLength={2000}
          placeholder="Why these amounts are appropriate"
          onChange={(e) => {
            setRationale(e.target.value);
          }}
          className="min-h-[90px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
        <p className="mt-2 text-[11.5px] text-ink-3">
          Recorded with your name. Sampling can start once it's decided.
        </p>
      </Fieldset>
      {decide.isError && <p className="text-meta text-danger">{errorMessage(decide.error)}</p>}
    </Sheet>
  );
}

function RiskFlags({ risk: r }: { risk: RiskOut }): JSX.Element | null {
  const flags: JSX.Element[] = [];
  if (r.significant)
    flags.push(
      <Badge key="sig" tone={r.needs_approval ? "warning" : "danger"}>
        {r.needs_approval ? "Significant · proposed" : "Significant"}
      </Badge>,
    );
  if (r.fraud === "presumed")
    flags.push(
      <Badge key="fraud" tone="danger">
        Fraud · presumed
      </Badge>,
    );
  if (r.fraud === "rebuttal")
    flags.push(
      <Badge key="reb" tone={r.needs_approval ? "warning" : "neutral"}>
        {r.needs_approval ? "Rebuttal proposed" : "Rebuttal approved"}
      </Badge>,
    );
  return flags.length > 0 ? <span className="flex flex-wrap gap-1">{flags}</span> : null;
}

function RiskRegister({
  engagementId,
  role,
}: {
  engagementId: string;
  role: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const risks = useQuery({ ...risksOptions(path), retry: false });
  const [editing, setEditing] = useState<RiskOut | "new" | null>(null);
  const approve = useMutation({
    ...approveRiskMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(risksQueryKey(path), data);
      toast.show("Approved");
    },
  });
  if (risks.isPending) return <Skeleton className="h-40" />;
  if (risks.isError)
    return <Alert title="Risks aren't available">{errorMessage(risks.error)}</Alert>;
  const rows = risks.data;
  const isPartner = role === "engagement_partner";
  const waiting = rows.filter((r) => r.needs_approval).length;
  const columns: Column<RiskOut>[] = [
    {
      key: "code",
      header: "",
      cell: (r) => <span className="font-mono text-[12px] text-ink-3">{r.code}</span>,
      sortValue: (r) => Number(r.code.slice(1)),
    },
    {
      key: "title",
      header: "Risk",
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-medium">{r.title}</span>
          <span className="text-[11.5px] text-ink-3">
            {[
              r.area,
              LEVEL[r.level],
              ...r.assertions.map((a) => ASSERTION[a as keyof typeof ASSERTION]),
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
      ),
      sortValue: (r) => r.title,
    },
    { key: "inherent", header: "Inherent", cell: (r) => RATING[r.inherent] },
    { key: "control", header: "Control", cell: (r) => RATING[r.control] },
    {
      key: "rmm",
      header: "RMM",
      cell: (r) => <StatusPill tone={RATING_TONE[r.rmm] ?? "neutral"}>{RATING[r.rmm]}</StatusPill>,
      sortValue: (r) => ["low", "moderate", "high"].indexOf(r.rmm),
    },
    { key: "flags", header: "Flags", cell: (r) => <RiskFlags risk={r} /> },
    {
      key: "approval",
      header: "Partner",
      cell: (r) =>
        r.needs_approval ? (
          isPartner ? (
            <Button
              size="sm"
              variant="outline"
              disabled={approve.isPending}
              onClick={(e) => {
                e.stopPropagation();
                approve.mutate({ ...path, path: { ...path.path, risk_id: r.id }, body: {} });
              }}
            >
              Approve
            </Button>
          ) : (
            <span className="text-[12px] text-ink-3">Waiting</span>
          )
        ) : r.approved_by_name != null ? (
          <span className="text-[12px] text-ink-3">{`Approved · ${r.approved_by_name}`}</span>
        ) : null,
    },
  ];
  return (
    <section
      aria-labelledby="risk-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="risk-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Risks of material misstatement
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">
          {[
            `${String(rows.length)} risks`,
            `${String(rows.filter((r) => r.significant).length)} significant`,
            ...(waiting > 0 ? [`${String(waiting)} waiting on the partner`] : []),
          ].join(" · ")}
        </span>
        <span className="flex-1" />
        {ASSESSORS.has(role) && (
          <Button
            size="sm"
            onClick={() => {
              setEditing("new");
            }}
          >
            Add risk
          </Button>
        )}
      </div>
      {approve.isError && (
        <p className="px-4 pt-2 text-meta text-danger">{errorMessage(approve.error)}</p>
      )}
      {rows.length === 0 ? (
        <EmptyState title="No risks yet">
          Record the risks of material misstatement, at the statement level or by assertion.
        </EmptyState>
      ) : (
        <DataTable
          label="Risk register"
          rows={rows}
          columns={columns}
          rowKey={(r) => r.id}
          {...(ASSESSORS.has(role)
            ? {
                onRowClick: (r: RiskOut) => {
                  setEditing(r);
                },
              }
            : {})}
        />
      )}
      {editing !== null && (
        <RiskSheet
          engagementId={engagementId}
          risk={editing === "new" ? undefined : editing}
          onClose={() => {
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}

function RiskSheet({
  engagementId,
  risk,
  onClose,
}: {
  engagementId: string;
  risk: RiskOut | undefined;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const [body, setBody] = useState<RiskBody>({
    title: risk?.title ?? "",
    area: risk?.area ?? "",
    level: risk?.level ?? "assertion",
    assertions: (risk?.assertions ?? []) as RiskBody["assertions"],
    inherent: risk?.inherent ?? "moderate",
    control: risk?.control ?? "maximum",
    significant: risk?.significant ?? false,
    fraud: risk?.fraud ?? "none",
    rationale: risk?.rationale ?? null,
  });
  const done = (data: RiskOut[]): void => {
    queryClient.setQueryData(risksQueryKey(path), data);
    toast.show(risk === undefined ? "Risk added" : "Risk revised");
    onClose();
  };
  const add = useMutation({ ...addRiskMutation(), onSuccess: done });
  const revise = useMutation({ ...reviseRiskMutation(), onSuccess: done });
  const asksWhy = body.significant === true || body.fraud === "rebuttal";
  const typedWhy = body.rationale ?? ""; // a person's words, not the agent's
  const why = typedWhy.trim();
  const valid = body.title.trim() !== "" && body.area.trim() !== "" && (!asksWhy || why !== "");
  const pending = add.isPending || revise.isPending;
  const error = add.error ?? revise.error;
  const select = "h-[30px] rounded-tile border-0 bg-nested px-2 inset-shadow-hair";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={risk === undefined ? "Add risk" : `Revise ${risk.code}`}
      footer={
        <Button
          disabled={!valid || pending}
          onClick={() => {
            const sent = { ...body, rationale: why === "" ? null : why };
            if (risk === undefined) add.mutate({ ...path, body: sent });
            else revise.mutate({ ...path, path: { ...path.path, risk_id: risk.id }, body: sent });
          }}
        >
          {risk === undefined ? "Add risk" : "Save new version"}
        </Button>
      }
    >
      <Fieldset title="Risk">
        <div className="flex flex-col gap-2 text-[13px]">
          <input
            aria-label="Risk title"
            value={body.title}
            maxLength={200}
            placeholder="What could go wrong"
            onChange={(e) => {
              setBody({ ...body, title: e.target.value });
            }}
            className="h-[30px] w-full rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair focus:bg-card"
          />
          <input
            aria-label="Area"
            value={body.area}
            maxLength={120}
            placeholder="Area, for example Revenue"
            onChange={(e) => {
              setBody({ ...body, area: e.target.value });
            }}
            className="h-[30px] w-full rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair focus:bg-card"
          />
          <label className="flex items-center justify-between gap-3">
            Level
            <select
              value={body.level}
              onChange={(e) => {
                setBody({ ...body, level: e.target.value as RiskBody["level"] });
              }}
              className={select}
            >
              {Object.entries(LEVEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {body.level === "assertion" && (
            <div className="flex flex-wrap gap-x-3 gap-y-1.5" role="group" aria-label="Assertions">
              {(Object.keys(ASSERTION) as RiskBody["assertions"]).map((a) => (
                <label key={a} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={body.assertions.includes(a)}
                    onChange={(e) => {
                      setBody({
                        ...body,
                        assertions: e.target.checked
                          ? [...body.assertions, a]
                          : body.assertions.filter((x) => x !== a),
                      });
                    }}
                  />
                  {ASSERTION[a]}
                </label>
              ))}
            </div>
          )}
        </div>
      </Fieldset>
      <Fieldset title="Assessment">
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Inherent risk
            <select
              value={body.inherent}
              onChange={(e) => {
                setBody({ ...body, inherent: e.target.value as RiskBody["inherent"] });
              }}
              className={select}
            >
              {["low", "moderate", "high"].map((k) => (
                <option key={k} value={k}>
                  {RATING[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center justify-between gap-3">
            Control risk
            <select
              value={body.control}
              onChange={(e) => {
                setBody({ ...body, control: e.target.value as RiskBody["control"] });
              }}
              className={select}
            >
              {["low", "moderate", "high", "maximum"].map((k) => (
                <option key={k} value={k}>
                  {RATING[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={body.significant === true}
              onChange={(e) => {
                setBody({ ...body, significant: e.target.checked });
              }}
            />
            Significant risk (the partner approves)
          </label>
          <label className="flex items-center justify-between gap-3">
            Fraud
            <select
              value={body.fraud}
              onChange={(e) => {
                setBody({ ...body, fraud: e.target.value as NonNullable<RiskBody["fraud"]> });
              }}
              className={select}
            >
              <option value="none">Not a fraud risk</option>
              <option value="presumed">Presumed fraud risk</option>
              <option value="rebuttal">Presumption rebutted (the partner approves)</option>
            </select>
          </label>
        </div>
      </Fieldset>
      <Fieldset title={asksWhy ? "Rationale (required)" : "Rationale"}>
        <textarea
          aria-label="Risk rationale"
          value={typedWhy}
          maxLength={2000}
          placeholder="Why, with the factors considered"
          onChange={(e) => {
            setBody({ ...body, rationale: e.target.value });
          }}
          className="min-h-[80px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
        />
        {risk !== undefined && (
          <p className="mt-2 text-[11.5px] text-ink-3">
            {`Saving keeps this version and adds a new one; a new version needs the partner's approval again. Last recorded by ${risk.recorded_by_name || "the team"}.`}
          </p>
        )}
      </Fieldset>
      {error != null && <p className="text-meta text-danger">{errorMessage(error)}</p>}
    </Sheet>
  );
}
