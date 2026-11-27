// TAX-14 fixture scenarios (T-08-T31, DEC-6037; docs/screens/TAX-14.md): Samuel Ito's run of the
// 1065 Review Checklist v4 on six open 1065s. The rows, the people's initials, Ridgeline's checks
// and the other versions are the Python scenario's (`seed/scenario.tax14-run.json`, `make
// fixtures`, never hand written): a running at 9:24 AM, b complete at 9:26 AM, c queued at
// 9:18 AM, d the standard picker open, e nothing selected.
import type { FirmOfficeOut, TaxPracticeRunOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { firmOffices } from "../seed/firm-people";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.tax14-run.json";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
export const TAX14_RUN = stableId("standards-run:1065-v4:2026-09-14");
const VERSION = stableId("standard-version:bh-1065-review-checklist:4");
export const RIDGELINE_ITEM = stableId("tax-return:ridgeline:2025:1065");
type Moment = "a" | "b" | "c";

const itemId = (client: string): string =>
  client.startsWith("Ridgeline") ? RIDGELINE_ITEM : stableId(`tax-return:${client}:2025`);

function chip(initials: string) {
  // The handoff names these people by initials only (01 §9.7): never invent a name.
  return { user_id: stableId(`person:${initials}`), initials, name: initials };
}

export function tax14Run(moment: Moment, offices: readonly FirmOfficeOut[]): TaxPracticeRunOut {
  const office = (name: string) => offices.find((o) => o.name === name)?.id ?? null;
  const items = exported.rows.map((r) => {
    const done = moment === "b" && r.status === "running";
    const queued = moment === "c";
    const status = queued ? "queued" : done ? "passed" : r.status;
    return {
      work_item_id: itemId(r.client_name),
      client_name: r.client_name,
      status: status as TaxPracticeRunOut["items"][number]["status"],
      checks_total: exported.checks_count,
      checks_passed: queued ? 0 : done ? exported.checks_count : r.checks_passed,
      exceptions: queued ? 0 : r.exceptions,
      linked_issues: queued ? 0 : r.linked_issues,
      created_issues: queued ? 0 : r.created_issues,
      issue_count: queued ? 0 : r.linked_issues + r.created_issues,
      office_id: office(r.office),
      preparer: chip(r.preparer),
      reviewer: chip(r.reviewer),
      return_status: r.return_status,
      review_level: r.review_level,
      completed_at: queued ? null : done ? exported.completed_at : r.completed_at,
    };
  });
  const count = (s: string) => items.filter((i) => i.status === s).length;
  return {
    run_id: TAX14_RUN,
    standard_version_id: VERSION,
    standard_label: `${exported.standard} v${String(exported.version_no)}`,
    form: "1065",
    status: moment === "c" ? "queued" : moment === "b" ? "complete" : "running",
    started_at: exported.started_at,
    completed_at: moment === "b" ? exported.completed_at : null,
    tiles: {
      selected: items.length,
      running: count("running"),
      passed: count("passed"),
      exceptions: count("exceptions"),
      queued: count("queued"),
    },
    items,
    allowed_actions: ["rerun"],
    version_no: exported.version_no,
    checks_count: exported.checks_count,
    started_by: exported.started_by,
  };
}

function at(state: string, clock: string, moment: Moment): Scenario {
  return {
    state,
    persona: "samuel-ito",
    clock,
    get handlers() {
      const offices = firmOffices();
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? "samuel-ito");
          return json({
            ...base,
            capabilities: [...base.capabilities, "standards_run.read", "standards_run.start"],
            flags: { ...base.flags, "tax.standards_runs": true },
          });
        },
        "GET /v1/firm/offices": () => json(offices),
        "GET /v1/standards-runs": () =>
          json({ items: [tax14Run(moment, offices)], next_cursor: null }),
        "GET /v1/standards-runs/{run_id}": () => json(tax14Run(moment, offices)),
        "GET /v1/standards-runs/{run_id}/items/{work_item_id}/checks": ({
          params,
        }: {
          params: Readonly<Record<string, string | undefined>>;
        }) =>
          json({
            items:
              params.work_item_id === RIDGELINE_ITEM
                ? exported.ridgeline_checks.map((c) => ({
                    result_id: stableId(`check:ridgeline:${c.code}`),
                    check_key: `1065-v4/${c.code}`,
                    display_code: c.code,
                    title: c.title,
                    outcome: c.outcome as "pass" | "exception",
                    difference: null,
                    linked_issue_id:
                      c.linked === null ? null : stableId(`issue:ridgeline:${c.code}`),
                    created_issue_id: null,
                    allowed_actions: [],
                  }))
                : [],
          }),
        "POST /v1/standards-runs/{run_id}:rerun": () => json(tax14Run("a", offices), 202),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-14T09:24:00-05:00", "a"), // Running
  b: at("b", "2026-09-14T09:26:00-05:00", "b"), // Complete
  c: at("c", "2026-09-14T09:18:00-05:00", "c"), // Queued
  d: at("d", "2026-09-14T09:24:00-05:00", "a"), // Standard picker
  e: at("e", "2026-09-14T09:24:00-05:00", "a"), // Empty selection
});

export type Tax14State = keyof typeof scenarios;

/** How each artboard opens: the picker open (d), nothing selected (e). */
export const INITIAL: Record<Tax14State, { picker?: boolean; selectNone?: boolean }> = {
  a: {},
  b: {},
  c: {},
  d: { picker: true },
  e: { selectNone: true },
};

/** The picker's other versions (D), the Python scenario's. */
export const OTHER_VERSIONS = exported.other_versions;
