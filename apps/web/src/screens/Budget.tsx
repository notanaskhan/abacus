import {
  getBudgetOptions,
  getBudgetQueryKey,
  listEngagementsOptions,
  meOptions,
  meteringOptions,
  putBudgetMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Input, Label, Panel, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";
import { AcknowledgeStep } from "./AcknowledgeStep";

function usd(value: string | number): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: "currency", currency: "USD" })
    : String(value);
}

/** SPEC-019 AC-3, AC-4: the firm's budget against spend, and spend by engagement and agent. */
export function Budget(): JSX.Element {
  const budget = useQuery(getBudgetOptions());
  const me = useQuery(meOptions());
  const tenant = me.data?.active_tenant_id ?? null;
  const isAdmin =
    me.data?.memberships.find((m) => m.tenant_id === tenant)?.firm_role === "firm_admin";
  return (
    <div className="flex flex-col gap-4">
      {budget.isPending ? (
        <Skeleton className="h-32" />
      ) : budget.isError ? (
        <Alert title="Couldn't load the budget">{errorMessage(budget.error)}</Alert>
      ) : (
        <BudgetPanel
          spent={Number(budget.data.spent_this_month_usd)}
          soft={Number(budget.data.monthly_soft_usd)}
          hard={Number(budget.data.monthly_hard_usd)}
          cap={Number(budget.data.plan_cap_usd)}
          isDefault={budget.data.is_default}
          canSet={isAdmin}
        />
      )}
      <Metering />
    </div>
  );
}

function BudgetPanel({
  spent,
  soft,
  hard,
  cap,
  isDefault,
  canSet,
}: {
  spent: number;
  soft: number;
  hard: number;
  cap: number;
  isDefault: boolean;
  canSet: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [newSoft, setNewSoft] = useState(String(soft));
  const [newHard, setNewHard] = useState(String(hard));
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    ...putBudgetMutation(),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: getBudgetQueryKey() });
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  const pct = Math.min(100, hard > 0 ? (spent / hard) * 100 : 0);
  const softPct = Math.min(100, hard > 0 ? (soft / hard) * 100 : 0);
  const state =
    spent >= hard ? "Hard limit reached" : spent >= soft ? "Soft limit passed" : "Within budget";
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    save.mutate({ body: { monthly_soft_usd: newSoft, monthly_hard_usd: newHard } });
  };
  return (
    <Panel
      title="This month's model spend"
      action={
        canSet && !editing ? (
          <span className="flex gap-2">
            <AcknowledgeStep step="budget" label="Looks right" />
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setEditing(true);
              }}
            >
              Set budget
            </Button>
          </span>
        ) : undefined
      }
    >
      <p className="text-sm">
        <span className="text-2xl font-semibold tabular-nums">{usd(spent)}</span>{" "}
        <span className="text-muted">
          of {usd(hard)} · {state}
          {isDefault && " · default budget"}
        </span>
      </p>
      <div
        role="meter"
        aria-label="Spend against the hard limit"
        aria-valuemin={0}
        aria-valuemax={hard}
        aria-valuenow={spent}
        className="relative h-3 overflow-hidden rounded-full bg-sunken"
      >
        <div
          className={`h-full ${spent >= soft ? "bg-warn" : "bg-accent"}`}
          style={{ width: `${String(pct)}%` }}
        />
        <div
          aria-hidden="true"
          className="absolute top-0 h-full w-0.5 bg-ink"
          style={{ left: `${String(softPct)}%` }}
        />
      </div>
      <p className="text-xs text-muted tabular-nums">
        Soft limit {usd(soft)} (deferrable work waits) · Hard limit {usd(hard)} (only essential
        work runs) · Plan limit {usd(cap)}
      </p>
      {editing && (
        <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <Label htmlFor="budget-soft">Soft limit (USD)</Label>
            <Input
              id="budget-soft"
              type="number"
              min={1}
              step="0.01"
              value={newSoft}
              onChange={(event) => {
                setNewSoft(event.target.value);
              }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="budget-hard">Hard limit (USD)</Label>
            <Input
              id="budget-hard"
              type="number"
              min={1}
              max={cap}
              step="0.01"
              value={newHard}
              onChange={(event) => {
                setNewHard(event.target.value);
              }}
            />
          </div>
          <Button type="submit" disabled={save.isPending}>
            Save
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setEditing(false);
            }}
          >
            Cancel
          </Button>
          {save.isError && !isForbidden(save.error) && (
            <p role="alert" className="w-full text-sm text-danger">
              {errorMessage(save.error) === "budget_invalid"
                ? "The soft limit must be above zero and at most the hard limit; the hard limit at most the plan limit."
                : errorMessage(save.error)}
            </p>
          )}
        </form>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}

type SortKey = "engagement" | "agent" | "cost";

function Metering(): JSX.Element {
  const [period, setPeriod] = useState<"day" | "month">("month");
  const [sort, setSort] = useState<SortKey>("cost");
  const metering = useQuery(meteringOptions({ query: { period } }));
  const engagements = useQuery(listEngagementsOptions());
  const names = new Map(
    (engagements.data ?? []).map((e) => [e.id, `${e.client_name} · ${e.name}`]),
  );
  const label = (id: string | null): string =>
    id === null ? "Firm-wide" : (names.get(id) ?? `Engagement ${id.slice(0, 8)}`);
  const rows = [...(metering.data ?? [])].sort((a, b) =>
    sort === "cost"
      ? Number(b.cost_usd) - Number(a.cost_usd)
      : sort === "agent"
        ? (a.agent_id ?? "").localeCompare(b.agent_id ?? "")
        : label(a.engagement_id).localeCompare(label(b.engagement_id)),
  );
  const total = rows.reduce((sum, r) => sum + Number(r.cost_usd), 0);
  const header = (key: SortKey, text: string): JSX.Element => (
    <Th aria-sort={sort === key ? (key === "cost" ? "descending" : "ascending") : "none"}>
      <button
        type="button"
        onClick={() => {
          setSort(key);
        }}
        className="font-semibold hover:underline"
      >
        {text}
      </button>
    </Th>
  );
  return (
    <Panel
      title="Spend by engagement and agent"
      action={
        <div role="group" aria-label="Period" className="flex gap-1">
          {(["day", "month"] as const).map((p) => (
            <Button
              key={p}
              size="sm"
              variant={period === p ? "default" : "outline"}
              aria-pressed={period === p}
              onClick={() => {
                setPeriod(p);
              }}
            >
              {p === "day" ? "Today" : "This month"}
            </Button>
          ))}
        </div>
      }
    >
      {metering.isPending ? (
        <Skeleton className="h-24" />
      ) : metering.isError ? (
        <Alert title="Couldn't load spend">{errorMessage(metering.error)}</Alert>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">No model spend in this period.</p>
      ) : (
        <div className="overflow-x-auto">
          <Table className="min-w-[520px]">
            <thead>
              <tr>
                {header("engagement", "Engagement")}
                {header("agent", "Agent")}
                {header("cost", "Cost")}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.engagement_id ?? "firm"}-${r.agent_id ?? "none"}`}>
                  <Td>{label(r.engagement_id)}</Td>
                  <Td className="text-muted">{r.agent_id ?? "—"}</Td>
                  <Td className="text-right tabular-nums">{usd(r.cost_usd)}</Td>
                </tr>
              ))}
              <tr>
                <Td className="font-semibold">Total</Td>
                <Td />
                <Td className="text-right font-semibold tabular-nums">{usd(total)}</Td>
              </tr>
            </tbody>
          </Table>
        </div>
      )}
    </Panel>
  );
}
