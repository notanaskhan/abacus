import type {
  LeadsheetOut,
  SnapshotOut,
  TrialBalanceDetailOut,
  TrialBalanceOut,
} from "@abacus/api-client";
import {
  adoptTbVersionMutation,
  adoptTrialBalanceMutation,
  annotateTbMutation,
  leadsheetsOptions,
  leadsheetsQueryKey,
  meOptions,
  tbCandidatesOptions,
  tbSignOffEqrMutation,
  tbSignOffManagerMutation,
  tbSignOffPartnerMutation,
  tbSignOffPrepareMutation,
  tbSignOffReviewMutation,
  teamOptions,
  trialBalanceOptions,
  trialBalanceQueryKey,
  trialBalancesOptions,
  trialBalancesQueryKey,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
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
import { amount } from "./amounts";
import { ReviewableNotes } from "./ReviewableNotes";
import { CheckStrip } from "./TieChecks";
import { LEVEL_SHORT } from "./Workpapers";

// SPEC-309 (TASK-320): the trial balance of record (AUD-06, first slice). The server computes
// every figure, total, the balance check, leadsheets and Δ% (ADR-050); this screen only shows
// them. Adopting a snapshot is a person's act; areas and WP refs annotate accounts, amounts never
// change.

export const LABEL: Record<TrialBalanceOut["label"], string> = {
  standard: "Standard",
  interim: "Interim",
  prior: "Prior",
  budget: "Budget",
  preliminary: "Preliminary",
};
const ADOPTERS = new Set(["engagement_partner", "manager", "senior", "staff"]);

/** "import_qbo_tb_csv" → "QuickBooks export"; connectors by name; never raw codes. */
export function sourceWord(source: string): string {
  if (source.startsWith("import_qbo")) return "a QuickBooks export";
  if (source.startsWith("import_netsuite")) return "a NetSuite export";
  if (source.startsWith("import_")) return "an imported file";
  if (source === "fake") return "the test connector";
  return "a connected ledger";
}

function day(iso: string): string {
  return iso.slice(0, 10);
}

function errorWord(code: string): string {
  const words: Record<string, string> = {
    trial_balance_exists: "This engagement already has a trial balance with that label.",
    snapshot_entity_mismatch: "That trial balance belongs to another entity.",
    tb_version_stale: "Someone adopted another version; reload to see it.",
    tb_same_snapshot: "That is already the current version.",
    no_assurance_item: "Only an audit or attest engagement holds a trial balance.",
    forbidden: "Your role can't do that on this engagement.",
  };
  return words[code] ?? code;
}

export function TrialBalance({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const list = useQuery({ ...trialBalancesOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? "";
  const [chosen, setChosen] = useState<string | null>(null);
  if (list.isPending) return <Skeleton className="h-64" />;
  if (list.isError) {
    return (
      <Alert title="The trial balance isn't available">
        {errorMessage(list.error) === "forbidden"
          ? "The trial balance is for the engagement team."
          : errorMessage(list.error)}
      </Alert>
    );
  }
  const tbs = list.data.trial_balances;
  const current = tbs.find((t) => t.id === chosen) ?? tbs[0];
  if (current === undefined) {
    return (
      <AdoptPanel
        engagementId={engagementId}
        snapshots={list.data.snapshots}
        canAdopt={ADOPTERS.has(role)}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {tbs.length > 1 && (
        <div role="group" aria-label="Trial balances" className="flex gap-1">
          {tbs.map((t) => (
            <Button
              key={t.id}
              size="sm"
              variant={t.id === current.id ? "primary" : "secondary"}
              aria-pressed={t.id === current.id}
              onClick={() => {
                setChosen(t.id);
              }}
            >
              {`TB: ${LABEL[t.label]} · ${t.period_end}`}
            </Button>
          ))}
        </div>
      )}
      <TrialBalanceCard
        engagementId={engagementId}
        tb={current}
        canAdopt={ADOPTERS.has(role)}
        snapshots={list.data.snapshots}
        role={role}
      />
    </div>
  );
}

function AdoptPanel({
  engagementId,
  snapshots,
  canAdopt,
}: {
  engagementId: string;
  snapshots: SnapshotOut[];
  canAdopt: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [snapshotId, setSnapshotId] = useState("");
  const [priorId, setPriorId] = useState("");
  const [label, setLabel] = useState<TrialBalanceOut["label"]>("standard");
  const adopt = useMutation({
    ...adoptTrialBalanceMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: trialBalancesQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
    onError: (e) => {
      toast.show(errorWord(errorMessage(e)));
    },
  });
  const picked = snapshots.find((s) => s.id === snapshotId);
  const priors = snapshots.filter((s) => picked !== undefined && s.period_end < picked.period_end);
  return (
    <section
      aria-labelledby="tb-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center border-b-[0.5px] border-hair px-4">
        <h2 id="tb-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Trial balance
        </h2>
      </div>
      {snapshots.length === 0 ? (
        <EmptyState title="No trial balance yet">
          Import the client's trial balance on a request, or ask the client to connect their
          ledger. It appears here to adopt.
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3 p-4">
          <p className="text-[13px] text-ink-2">
            Choose the trial balance this engagement's working papers read from. It never changes
            once adopted; a newer one becomes the next version.
          </p>
          <Fieldset title="Trial balance">
            <div className="flex flex-col gap-1 text-[13px]">
              {snapshots.map((s) => (
                <label key={s.id} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="snapshot"
                    checked={snapshotId === s.id}
                    disabled={!canAdopt}
                    onChange={() => {
                      setSnapshotId(s.id);
                      setPriorId("");
                    }}
                  />
                  <span className="tabular-nums">{`${s.period_start} – ${s.period_end}`}</span>
                  <span className="text-ink-3">
                    {`from ${sourceWord(s.source)}, pulled ${day(s.pulled_at)} · ${String(s.line_count)} accounts`}
                  </span>
                </label>
              ))}
            </div>
          </Fieldset>
          {picked !== undefined && (
            <Fieldset title="Beginning of year (optional)">
              {priors.length === 0 ? (
                <p className="text-[12.5px] text-ink-3">
                  No earlier trial balance for this entity.
                </p>
              ) : (
                <select
                  aria-label="Prior-year trial balance"
                  value={priorId}
                  onChange={(e) => {
                    setPriorId(e.target.value);
                  }}
                  className="h-[30px] rounded-tile border-0 bg-nested px-2 text-[13px] inset-shadow-hair"
                >
                  <option value="">None</option>
                  {priors.map((s) => (
                    <option key={s.id} value={s.id}>
                      {`${s.period_start} – ${s.period_end}, pulled ${day(s.pulled_at)}`}
                    </option>
                  ))}
                </select>
              )}
            </Fieldset>
          )}
          <div className="flex items-center gap-2">
            <select
              aria-label="Label"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value as TrialBalanceOut["label"]);
              }}
              className="h-[30px] rounded-tile border-0 bg-nested px-2 text-[13px] inset-shadow-hair"
            >
              {Object.entries(LABEL).map(([code, word]) => (
                <option key={code} value={code}>{`TB: ${word}`}</option>
              ))}
            </select>
            <Button
              disabled={!canAdopt || snapshotId === "" || adopt.isPending}
              onClick={() => {
                adopt.mutate({
                  path: { engagement_id: engagementId },
                  body: {
                    snapshot_id: snapshotId,
                    label,
                    ...(priorId === "" ? {} : { prior_snapshot_id: priorId }),
                  },
                });
              }}
            >
              Use this trial balance
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function TrialBalanceCard({
  engagementId,
  tb,
  canAdopt,
  snapshots,
  role,
}: {
  engagementId: string;
  tb: TrialBalanceOut;
  canAdopt: boolean;
  snapshots: SnapshotOut[];
  role: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, tb_id: tb.id } };
  const detail = useQuery({ ...trialBalanceOptions(path), retry: false });
  const candidates = useQuery({ ...tbCandidatesOptions(path), retry: false });
  const [mode, setMode] = useState<"accounts" | "leadsheets">("accounts");
  const [layer, setLayer] = useState<"unadjusted" | "final">("unadjusted");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [annotating, setAnnotating] = useState(false);
  const [upgrading, setUpgrading] = useState<SnapshotOut | null>(null);
  const fresh = (data: TrialBalanceDetailOut): void => {
    queryClient.setQueryData(trialBalanceQueryKey(path), data);
    void queryClient.invalidateQueries({ queryKey: leadsheetsQueryKey(path) });
    void queryClient.invalidateQueries({
      queryKey: trialBalancesQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  if (detail.isPending) return <Skeleton className="h-96" />;
  if (detail.isError) {
    return <Alert title="The trial balance isn't available">{errorMessage(detail.error)}</Alert>;
  }
  const d = detail.data;
  const unit = d.trial_balance.display_unit;
  const newer = (candidates.data ?? []).find(
    (c) =>
      c.id !== d.version.snapshot_id &&
      (c.lines_changed ?? 0) > 0 &&
      c.pulled_at > d.version.pulled_at,
  );
  const hasPrior = d.boy !== null;
  const showFinal = layer === "final" && d.final != null;
  return (
    <section
      aria-labelledby="tb-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] flex-wrap items-center gap-2 border-b-[0.5px] border-hair px-4 py-2">
        <h2 id="tb-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Trial balance
        </h2>
        <StatusPill tone="neutral">{`${showFinal ? "Final" : "Unadjusted"} · TB: ${LABEL[d.trial_balance.label]}`}</StatusPill>
        <span className="text-[12.5px] text-ink-3 tabular-nums">
          {`${d.trial_balance.period_end} · v${String(d.version.version_no)}`}
        </span>
        {(showFinal ? d.final : d.eoy)?.balanced !== false ? (
          <StatusPill tone="success">Balanced</StatusPill>
        ) : (
          <StatusPill tone="danger">{`Off ${amount((showFinal ? d.final : d.eoy)?.difference)}`}</StatusPill>
        )}
        <span className="flex-1" />
        <div role="group" aria-label="Layer" className="flex gap-1">
          {(["unadjusted", "final"] as const).map((x) => (
            <Button
              key={x}
              size="sm"
              variant={layer === x ? "primary" : "secondary"}
              aria-pressed={layer === x}
              disabled={x === "final" && !d.layers_available}
              title={
                x === "final" && !d.layers_available
                  ? "Adjustments arrive with Findings & adjustments"
                  : undefined
              }
              onClick={() => {
                setLayer(x);
              }}
            >
              {x === "unadjusted" ? "Unadjusted" : "Final"}
            </Button>
          ))}
        </div>
        <div role="group" aria-label="View" className="flex gap-1">
          {(["accounts", "leadsheets"] as const).map((m) => (
            <Button
              key={m}
              size="sm"
              variant={mode === m ? "primary" : "secondary"}
              aria-pressed={mode === m}
              onClick={() => {
                setMode(m);
              }}
            >
              {m === "accounts" ? "Accounts" : "Leadsheets"}
            </Button>
          ))}
        </div>
      </div>
      <p className="border-b-[0.5px] border-hair px-4 py-1.5 text-[12px] text-ink-3">
        {`Adopted by ${d.version.adopted_by_name} from ${sourceWord(d.version.source)}, pulled ${day(d.version.pulled_at)}`}
        {d.version.reason != null && ` · ${d.version.reason}`}
      </p>
      {showFinal && d.pending_entries > 0 && (
        <p className="border-b-[0.5px] border-hair px-4 py-1.5 text-[12px] text-ink-3">
          {`${String(d.pending_entries)} proposed ${d.pending_entries === 1 ? "entry isn't" : "entries aren't"} in Final until approved.`}
        </p>
      )}
      <CheckStrip
        engagementId={engagementId}
        tbId={tb.id}
        canDefine={canAdopt}
        selected={[...picked]}
      />
      {newer !== undefined && (
        <div className="flex items-center gap-2 border-b-[0.5px] border-hair bg-amber-tint px-4 py-2 text-[12.5px]">
          <span>
            {`A newer trial balance is available · pulled ${day(newer.pulled_at)} · ${String(newer.lines_changed)} ${newer.lines_changed === 1 ? "line" : "lines"} changed`}
          </span>
          <span className="flex-1" />
          {canAdopt && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setUpgrading(newer);
              }}
            >
              {`Use v${String(d.trial_balance.current_version_no + 1)}…`}
            </Button>
          )}
        </div>
      )}
      {mode === "accounts" ? (
        <>
          {canAdopt && (
            <div className="flex items-center gap-2 px-4 py-2">
              <span className="text-[12.5px] text-ink-3 tabular-nums">
                {picked.size === 0
                  ? "Select accounts to set an area or WP ref"
                  : `${String(picked.size)} selected`}
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={picked.size === 0}
                onClick={() => {
                  setAnnotating(true);
                }}
              >
                Set area and WP ref
              </Button>
            </div>
          )}
          <div className="max-h-[640px] overflow-auto">
            <table className="w-full border-collapse text-[12.5px]">
              <thead className="sticky top-0 z-10 bg-band-hd text-ink-3">
                <tr>
                  {canAdopt && (
                    <th className="w-[32px] px-2 py-1.5">
                      <input
                        type="checkbox"
                        aria-label="Select all accounts"
                        checked={picked.size === d.lines.length && d.lines.length > 0}
                        onChange={(e) => {
                          setPicked(
                            e.target.checked
                              ? new Set(d.lines.map((l) => l.account_code))
                              : new Set(),
                          );
                        }}
                      />
                    </th>
                  )}
                  <th scope="col" className="px-2 py-1.5 text-left font-medium">
                    Account
                  </th>
                  <th scope="col" className="px-2 py-1.5 text-left font-medium">
                    Area
                  </th>
                  <th scope="col" className="px-2 py-1.5 text-left font-medium">
                    WP ref
                  </th>
                  {hasPrior && (
                    <th scope="col" className="px-2 py-1.5 text-right font-medium">
                      Beginning of year
                    </th>
                  )}
                  <th scope="col" className="px-2 py-1.5 text-right font-medium">
                    Debit
                  </th>
                  <th scope="col" className="px-2 py-1.5 text-right font-medium">
                    Credit
                  </th>
                  <th scope="col" className="px-2 py-1.5 text-right font-medium">
                    End of year
                  </th>
                  {showFinal && (
                    <>
                      <th scope="col" className="px-2 py-1.5 text-right font-medium">
                        AJE
                      </th>
                      <th scope="col" className="px-2 py-1.5 text-right font-medium">
                        RJE
                      </th>
                      <th scope="col" className="px-2 py-1.5 text-right font-medium">
                        Final
                      </th>
                    </>
                  )}
                  {hasPrior && (
                    <th scope="col" className="px-2 py-1.5 text-right font-medium">
                      Change
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {d.lines.map((l) => (
                  <tr key={l.account_code} className="border-t-[0.5px] border-hair">
                    {canAdopt && (
                      <td className="px-2 py-1">
                        <input
                          type="checkbox"
                          aria-label={`Select ${l.account_code}`}
                          checked={picked.has(l.account_code)}
                          onChange={(e) => {
                            const next = new Set(picked);
                            if (e.target.checked) next.add(l.account_code);
                            else next.delete(l.account_code);
                            setPicked(next);
                          }}
                        />
                      </td>
                    )}
                    <td className="px-2 py-1">
                      <span className="mr-2 tabular-nums text-ink-3">{l.account_code}</span>
                      {l.account_name}
                    </td>
                    <td className="px-2 py-1 text-ink-2">
                      {l.area ?? <span className="text-ink-4">—</span>}
                    </td>
                    <td className="px-2 py-1 tabular-nums">
                      {l.wp_ref ?? <span className="text-ink-4">—</span>}
                    </td>
                    {hasPrior && (
                      <td className="px-2 py-1 text-right tabular-nums">{amount(l.boy, unit)}</td>
                    )}
                    <td className="px-2 py-1 text-right tabular-nums">{amount(l.debit, unit)}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{amount(l.credit, unit)}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{amount(l.eoy, unit)}</td>
                    {showFinal && (
                      <>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {l.aje != null && l.aje !== "0.00" ? amount(l.aje, unit) : ""}
                          {l.refs.length > 0 && (
                            <span className="ml-1.5 text-[10.5px] font-medium text-accent">
                              {l.refs.join(" ")}
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {l.rje != null && l.rje !== "0.00" ? amount(l.rje, unit) : ""}
                        </td>
                        <td className="px-2 py-1 text-right font-medium tabular-nums">
                          {amount(l.final, unit)}
                        </td>
                      </>
                    )}
                    {hasPrior && (
                      <td className="px-2 py-1 text-right tabular-nums">
                        {amount(l.change, unit)}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-[0.5px] border-hair font-medium">
                  {canAdopt && <td />}
                  <td className="px-2 py-1.5" colSpan={3}>
                    Total
                  </td>
                  {hasPrior && <td />}
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {amount(d.eoy.debit, unit)}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {amount(d.eoy.credit, unit)}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {amount(d.eoy.difference, unit)}
                  </td>
                  {showFinal && (
                    <>
                      <td />
                      <td />
                      <td
                        className="px-2 py-1.5 text-right tabular-nums"
                        title={`Final debits ${amount(d.final?.debit, unit)} · credits ${amount(d.final?.credit, unit)}`}
                      >
                        {amount(d.final?.difference, unit)}
                      </td>
                    </>
                  )}
                  {hasPrior && <td />}
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      ) : (
        <Leadsheets
          engagementId={engagementId}
          tbId={tb.id}
          unit={unit}
          layer={showFinal ? "final" : "unadjusted"}
        />
      )}
      <div className="grid gap-3 border-t-[0.5px] border-hair p-4 lg:grid-cols-2">
        <TbSignOffs path={path} detail={d} role={role} onDone={fresh} />
        <div>
          <h3 className="mb-1 text-[13px] font-medium">Review notes</h3>
          <ReviewableNotes
            engagementId={engagementId}
            targetType="trial_balance"
            targetId={tb.id}
            anchor={picked.size === 1 ? [...picked][0] : null}
            anchorLabel={picked.size === 1 ? `account ${[...picked][0] ?? ""}` : undefined}
            role={role}
          />
        </div>
      </div>
      {d.versions.length > 1 && (
        <div className="border-t-[0.5px] border-hair px-4 py-2">
          <h3 className="mb-1 text-[12.5px] font-medium text-ink-2">Versions</h3>
          <ul className="flex flex-col gap-0.5 text-[12px] text-ink-3">
            {d.versions.map((v) => (
              <li key={v.version_no}>
                {`v${String(v.version_no)} · ${v.adopted_by_name} · ${day(v.adopted_at)}${v.reason != null ? ` · ${v.reason}` : ""}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      {annotating && (
        <AnnotateSheet
          path={path}
          codes={[...picked]}
          onClose={() => {
            setAnnotating(false);
          }}
          onDone={(data) => {
            fresh(data);
            setPicked(new Set());
            setAnnotating(false);
          }}
        />
      )}
      {upgrading !== null && (
        <VersionSheet
          path={path}
          snapshot={upgrading}
          seen={d.trial_balance.current_version_no}
          priorId={d.version.prior_snapshot_id}
          priors={snapshots.filter((s) => s.period_end < upgrading.period_end)}
          onClose={() => {
            setUpgrading(null);
          }}
          onDone={(data) => {
            fresh(data);
            setUpgrading(null);
          }}
        />
      )}
    </section>
  );
}

type TbPath = { path: { engagement_id: string; tb_id: string } };

const LEVEL_ROLES: Record<number, readonly string[]> = {
  1: ["manager", "senior", "staff"],
  2: ["engagement_partner", "manager", "senior"],
  3: ["engagement_partner", "manager"],
  4: ["engagement_partner"],
  5: ["reviewer"],
};
const LEVEL_TITLE: Record<number, string> = {
  1: "Preparer",
  2: "Reviewer",
  3: "Manager",
  4: "Partner",
  5: "Quality reviewer",
};

/** SPEC-313 (TASK-331): sign the trial balance's current version and annotations. */
function TbSignOffs({
  path,
  detail,
  role,
  onDone,
}: {
  path: TbPath;
  detail: TrialBalanceDetailOut;
  role: string;
  onDone: (d: TrialBalanceDetailOut) => void;
}): JSX.Element {
  const opts = {
    onSuccess: onDone,
    onError: (e: unknown) => {
      const code = errorMessage(e);
      toast.show(
        code === "review_notes_open"
          ? "Clear the open review notes before signing as a reviewer."
          : code === "not_prepared"
            ? "The preparer signs first."
            : code === "preparer_cannot_review"
              ? "Someone other than the preparer reviews."
              : code,
      );
    },
  };
  const sign = {
    1: useMutation({ ...tbSignOffPrepareMutation(), ...opts }),
    2: useMutation({ ...tbSignOffReviewMutation(), ...opts }),
    3: useMutation({ ...tbSignOffManagerMutation(), ...opts }),
    4: useMutation({ ...tbSignOffPartnerMutation(), ...opts }),
    5: useMutation({ ...tbSignOffEqrMutation(), ...opts }),
  } as const;
  const preparer = detail.sign_offs.find((l) => l.level === 1);
  const prepared = preparer?.signed_by_name != null && !preparer.stale;
  return (
    <div>
      <h3 className="mb-1 text-[13px] font-medium">Sign-offs</h3>
      <ul className="flex flex-col gap-1 text-[12.5px]">
        {detail.sign_offs.map((l) => {
          const signed = l.signed_by_name != null;
          const current = signed && !l.stale;
          const mutation = sign[l.level as 1 | 2 | 3 | 4 | 5];
          return (
            <li key={l.level} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={
                  "inline-flex h-[20px] min-w-[28px] items-center justify-center rounded-[3px] text-[10.5px] font-medium " +
                  (signed
                    ? l.stale
                      ? "bg-amber-tint text-ink-2 line-through"
                      : "bg-green-tint text-ink"
                    : "bg-nested text-ink-4 inset-shadow-hair")
                }
              >
                {LEVEL_SHORT[l.name]}
              </span>
              <span>{LEVEL_TITLE[l.level]}</span>
              <span className="text-ink-3">
                {signed
                  ? `${l.signed_by_name ?? ""}${l.stale ? " · changed since" : ""}`
                  : "Not signed"}
              </span>
              <span className="flex-1" />
              {(LEVEL_ROLES[l.level] ?? []).includes(role) && !current && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={(l.level > 1 && !prepared) || mutation.isPending}
                  onClick={() => {
                    mutation.mutate({ ...path });
                  }}
                >
                  {l.stale ? "Sign again" : "Sign off"}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Leadsheets({
  engagementId,
  tbId,
  unit,
  layer,
}: {
  engagementId: string;
  tbId: string;
  unit: string;
  layer: "unadjusted" | "final";
}): JSX.Element {
  const sheets = useQuery({
    ...leadsheetsOptions({
      path: { engagement_id: engagementId, tb_id: tbId },
      query: { layer },
    }),
    retry: false,
  });
  if (sheets.isPending) return <Skeleton className="m-4 h-40" />;
  if (sheets.isError)
    return <Alert title="Leadsheets aren't available">{errorMessage(sheets.error)}</Alert>;
  return (
    <div className="flex flex-col gap-3 p-4">
      {sheets.data.map((s) => (
        <LeadsheetTable key={s.area} sheet={s} unit={unit} />
      ))}
    </div>
  );
}

function pctWord(value: string | null | undefined): string {
  return value == null ? "—" : `${value} %`;
}

function LeadsheetTable({ sheet, unit }: { sheet: LeadsheetOut; unit: string }): JSX.Element {
  const hasPrior = sheet.py != null;
  return (
    <section aria-label={`${sheet.area} leadsheet`} className="rounded-nested bg-card shadow-e1">
      <h3 className="border-b-[0.5px] border-hair px-3 py-2 text-[13px] font-medium">
        {sheet.area}
        <span className="ml-2 text-[12px] font-normal text-ink-3 tabular-nums">
          {sheet.rows.length}
        </span>
      </h3>
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="text-ink-3">
          <tr>
            <th scope="col" className="px-3 py-1 text-left font-medium">
              Account
            </th>
            {hasPrior && (
              <th scope="col" className="px-3 py-1 text-right font-medium">
                PY
              </th>
            )}
            <th scope="col" className="px-3 py-1 text-right font-medium">
              CY
            </th>
            {hasPrior && (
              <th scope="col" className="px-3 py-1 text-right font-medium">
                Δ
              </th>
            )}
            {hasPrior && (
              <th scope="col" className="px-3 py-1 text-right font-medium">
                Δ%
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {sheet.rows.map((r) => (
            <tr key={r.account_code} className="border-t-[0.5px] border-hair">
              <td className="px-3 py-1">
                <span className="mr-2 tabular-nums text-ink-3">{r.account_code}</span>
                {r.account_name}
              </td>
              {hasPrior && (
                <td className="px-3 py-1 text-right tabular-nums">{amount(r.py, unit)}</td>
              )}
              <td className="px-3 py-1 text-right tabular-nums">{amount(r.cy, unit)}</td>
              {hasPrior && (
                <td className="px-3 py-1 text-right tabular-nums">{amount(r.change, unit)}</td>
              )}
              {hasPrior && (
                <td className="px-3 py-1 text-right tabular-nums">{pctWord(r.change_pct)}</td>
              )}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-[0.5px] border-hair font-medium">
            <td className="px-3 py-1.5">{`Total ${sheet.area.toLowerCase()}`}</td>
            {hasPrior && (
              <td className="px-3 py-1.5 text-right tabular-nums">{amount(sheet.py, unit)}</td>
            )}
            <td className="px-3 py-1.5 text-right tabular-nums">{amount(sheet.cy, unit)}</td>
            {hasPrior && (
              <td className="px-3 py-1.5 text-right tabular-nums">{amount(sheet.change, unit)}</td>
            )}
            {hasPrior && (
              <td className="px-3 py-1.5 text-right tabular-nums">{pctWord(sheet.change_pct)}</td>
            )}
          </tr>
        </tfoot>
      </table>
    </section>
  );
}

const WP_REF = /^[A-Z0-9][A-Z0-9.-]{0,19}$/;

function AnnotateSheet({
  path,
  codes,
  onClose,
  onDone,
}: {
  path: TbPath;
  codes: string[];
  onClose: () => void;
  onDone: (d: TrialBalanceDetailOut) => void;
}): JSX.Element {
  const [area, setArea] = useState("");
  const [wpRef, setWpRef] = useState("");
  const save = useMutation({
    ...annotateTbMutation(),
    onSuccess: onDone,
    onError: (e) => {
      toast.show(errorWord(errorMessage(e)));
    },
  });
  const ref = wpRef.trim().toUpperCase();
  const ok = (area.trim() !== "" || ref !== "") && (ref === "" || WP_REF.test(ref));
  const input = "h-[30px] w-[240px] rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Set area and WP ref · ${String(codes.length)} ${codes.length === 1 ? "account" : "accounts"}`}
      footer={
        <Button
          disabled={!ok || save.isPending}
          onClick={() => {
            save.mutate({
              ...path,
              body: {
                accounts: codes.map((code) => ({
                  account_code: code,
                  ...(area.trim() === "" ? {} : { area: area.trim() }),
                  ...(ref === "" ? {} : { wp_ref: ref }),
                })),
              },
            });
          }}
        >
          Save
        </Button>
      }
    >
      <Fieldset>
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Audit area
            <input
              value={area}
              maxLength={120}
              placeholder="Cash"
              onChange={(e) => {
                setArea(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            WP ref
            <input
              value={wpRef}
              maxLength={20}
              placeholder="C-100"
              onChange={(e) => {
                setWpRef(e.target.value);
              }}
              className={input}
            />
          </label>
          <p className="text-[12px] text-ink-3">
            A blank field clears it on the selected accounts. Amounts can't be edited.
          </p>
        </div>
      </Fieldset>
    </Sheet>
  );
}

function VersionSheet({
  path,
  snapshot,
  seen,
  priorId,
  priors,
  onClose,
  onDone,
}: {
  path: TbPath;
  snapshot: SnapshotOut;
  seen: number;
  priorId: string | null | undefined;
  priors: SnapshotOut[];
  onClose: () => void;
  onDone: (d: TrialBalanceDetailOut) => void;
}): JSX.Element {
  const [reason, setReason] = useState("");
  const [prior, setPrior] = useState(priorId ?? "");
  const adopt = useMutation({
    ...adoptTbVersionMutation(),
    onSuccess: onDone,
    onError: (e) => {
      toast.show(errorWord(errorMessage(e)));
    },
  });
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Use v${String(seen + 1)}`}
      footer={
        <Button
          disabled={reason.trim() === "" || adopt.isPending}
          onClick={() => {
            adopt.mutate({
              ...path,
              body: {
                snapshot_id: snapshot.id,
                reason: reason.trim(),
                seen_version: seen,
                ...(prior === "" ? {} : { prior_snapshot_id: prior }),
              },
            });
          }}
        >
          Adopt
        </Button>
      }
    >
      <Fieldset title="The newer trial balance">
        <p className="text-[13px]">
          {`From ${sourceWord(snapshot.source)}, pulled ${day(snapshot.pulled_at)} · ${String(snapshot.lines_changed ?? 0)} lines changed`}
        </p>
        {priors.length > 0 && (
          <select
            aria-label="Prior-year trial balance"
            value={prior}
            onChange={(e) => {
              setPrior(e.target.value);
            }}
            className="mt-2 h-[30px] rounded-tile border-0 bg-nested px-2 text-[13px] inset-shadow-hair"
          >
            <option value="">No beginning of year</option>
            {priors.map((s) => (
              <option key={s.id} value={s.id}>
                {`${s.period_start} – ${s.period_end}, pulled ${day(s.pulled_at)}`}
              </option>
            ))}
          </select>
        )}
      </Fieldset>
      <Fieldset title="Why">
        <textarea
          aria-label="Reason"
          value={reason}
          maxLength={500}
          onChange={(e) => {
            setReason(e.target.value);
          }}
          className="h-[80px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair"
        />
        <p className="mt-1 text-[12px] text-ink-3">
          Earlier versions stay as they were; sign-offs on them show the change.
        </p>
      </Fieldset>
    </Sheet>
  );
}
