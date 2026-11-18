// ADM-14 fixture reads (G-04-T18, DEC-5639): Brightwater Hale's plan, usage, alerts, billing rates
// and engagement budgets per artboard, built from the Python scenario's export
// (`scenario.adm14.json`, `make fixtures`; no figure is typed here).
import type {
  BillingRatesOut,
  BudgetAlertsOut,
  EngagementBudgetsOut,
  FirmPlanOut,
  FirmUsageOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import exported from "./scenario.adm14.json";

export type Adm14State = "a" | "b" | "c" | "d" | "e" | "f";
export const CLOCKS = exported.clocks as Readonly<Record<Adm14State, string>>;
const PEOPLE = exported.people as Readonly<Record<string, string>>;

function person(name: string) {
  return { display_name: name, user_id: PEOPLE[name] ?? stableId(`user:${name}`) };
}

export function usage(state: Adm14State): FirmUsageOut {
  const key = state === "b" || state === "c" ? state : "a";
  return exported.usage[key] as FirmUsageOut;
}

export function plan(): FirmPlanOut {
  const t = exported.term;
  return {
    plan_code: "annual",
    term_start: t.start,
    term_end: t.end,
    renewal_on: t.renewal_on,
    renewal_in_days: 92,
    billing_contact: person("Grace Holloway"),
    seats: { total: exported.seats, used: exported.seats, pending: 0, full: true },
    included_agent_minutes: exported.usage.a.included_minutes,
    usage_month_anchor_day: 15,
    modules: exported.modules as FirmPlanOut["modules"],
    library_channel: "stable",
    workbench_active_30d: exported.workbench_active_30d,
    version: 1,
  };
}

export function alerts(): BudgetAlertsOut {
  return {
    rules: exported.alerts.map((r) => ({
      id: stableId(`budget-alert:${r.threshold_pct}`),
      enabled: true,
      threshold_pct: r.threshold_pct,
      threshold_minutes: r.threshold_minutes,
      recipients: r.recipients,
      recipient_groups: r.recipient_groups as ("partners" | "firm_admins")[],
    })),
    at_100_behaviour: "keep_running",
    engagement_default_minutes: exported.engagement_default_minutes,
    engagement_alert_pct: exported.engagement_alert_pct,
    partner_approver: person("Margaret Okonkwo"),
    version: 1,
    updated_by: null,
    updated_at: null,
  };
}

export function budgets(): EngagementBudgetsOut {
  const g = exported.granite;
  return {
    counts: { total: 1 },
    items: [{ engagement_id: stableId("engagement:granite-peak-fy2026-fs-audit"), ...g }],
    next_cursor: null,
  };
}

export function rates(): BillingRatesOut {
  return {
    connected: true,
    provider_key: "cch_axcess_practice",
    effective_from: "2026-01-01",
    synced_at: "2026-10-01T09:00:00-05:00",
    bands: exported.rates,
  };
}

export const RATES_PEOPLE = exported.rates_people;
