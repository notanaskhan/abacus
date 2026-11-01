// EBP-01 Plan profile & service providers (A-05-T11): the A-05-T10 shapes for Northwind PY2025,
// figures verbatim from the handoff spec and the A-05-T07 golden (tests/golden/ebp). Masked TINs
// only: no full EIN exists in the fixture (P-12).
import type { PlanOut, ProviderOut, ProvidersOut } from "@abacus/api-client";

export type Ebp01Variant = "a" | "b" | "c" | "d";

const PLAN: PlanOut = {
  plan_name: "Northwind Robotics 401(k) Plan",
  plan_number: "001",
  sponsor_ein: null,
  plan_year_start: "2025-01-01",
  plan_year_end: "2025-12-31",
  plan_type: "401k",
  safe_harbor: "qaca",
  recordkeeper_id: "58217",
  participants_boy: 286,
  participants_eoy: 301,
  filer_status: "large_plan",
  form5500_due_on: "2026-10-15",
  audit_kind: "103a3c",
  allowed_actions: ["ebp_plan.edit"],
};

const id = (n: number): string => `00000000-0000-4000-8000-0000000005${String(n).padStart(2, "0")}`;

const KEYSTONE: ProviderOut = {
  id: id(1),
  name: "Keystone Retirement Services",
  role: "recordkeeper",
  ein: null,
  status: "waiting_on_inputs",
  soc_report: "SOC 1 Type 2, Oct 1 to Sep 30, 2025",
  check_note: null,
};
const HARBORLINE: ProviderOut = {
  id: id(2),
  name: "Harborline Trust Company",
  role: "trustee",
  ein: null,
  status: "received",
  soc_report: "SOC 1 Type 2, Jan 1 to Dec 31, 2025",
  check_note: null,
};
const PAYGRID: ProviderOut = {
  id: id(3),
  name: "PayGrid Payroll",
  role: "other",
  ein: null,
  status: "received",
  soc_report: "SOC 1 Type 2, Jan 1 to Dec 31, 2025",
  check_note: null,
};
const SUMMIT: ProviderOut = {
  id: id(4),
  name: "Summit Plan Administrators",
  role: "tpa",
  ein: null,
  status: "received",
  soc_report: null,
  check_note: null,
};

export function ebp01Plan(variant: Ebp01Variant): PlanOut {
  return variant === "b" ? { ...PLAN, plan_number: null } : PLAN;
}

export function ebp01Providers(variant: Ebp01Variant): ProvidersOut {
  const items =
    variant === "c"
      ? [
          {
            ...KEYSTONE,
            status: "correction_requested" as const,
            check_note:
              "Summit's draft Schedule C lists Keystone Retirement Svcs LLC, EIN ending 4402; the Keystone service agreement shows EIN ending 4420",
          },
          HARBORLINE,
          PAYGRID,
          { ...SUMMIT, status: "correction_requested" as const },
        ]
      : [KEYSTONE, HARBORLINE, PAYGRID, SUMMIT];
  return { items, allowed_actions: ["ebp_provider.manage", "ebp_provider.invite"] };
}
