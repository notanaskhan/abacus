// SHT-02 fixture scenarios (K-03-T09; K-03-T23, DEC-6034; SH-1): the column drawer over BH-FS-430.
// Each artboard's persona and clock. The Service period column and its usage are the Python
// scenario's (`seed/scenario.sht02-column.json`, `make fixtures`, never hand written): a is the
// new column at Thu Sep 24 11:20 AM (SHT-01 c behind it, no Service period yet), b its type
// picker, c the edit on Wed Sep 30 9:50 AM once two views and the Conclusion agent column use it,
// d the Date → Text warning, e the blocked delete, f Simone Baptiste, who may not configure.
import type { SheetColumnOut, SheetVmOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.sht02-column.json";
import { rows, sheet } from "../seed/sheets-sh1";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const ENGAGEMENT = stableId("engagement:granite-peak:fy2026");

/** The Service period column in the sheets contract's shape (c to e edit it). */
export const SERVICE_PERIOD: SheetColumnOut = {
  column_id: stableId("sheet-column:service_period"),
  key: exported.column.key,
  type: exported.column.type as SheetColumnOut["type"],
  label: exported.column.label,
  width: 124,
  frozen: false,
  options: [],
  description: exported.column.description,
  date_range: exported.column.date_range,
  display: exported.column.display as "date" | "month",
  required: exported.column.required,
  validation: exported.column.validation as "end_on_or_after_start",
  classification: exported.column.classification as "restricted",
  visible_to_client: exported.column.visible_to_client,
};
export const AFTER_KEY = exported.column.after_key;

function vm(editing: boolean): SheetVmOut {
  const base = sheet("filled");
  // Before 11:20 AM the sheet has no Service period (SHT-01 c); the edit states have it.
  const columns = base.columns.flatMap((c) =>
    c.key === SERVICE_PERIOD.key ? (editing ? [SERVICE_PERIOD] : []) : [c],
  );
  return { ...base, columns, engagement_id: ENGAGEMENT, configurer: exported.manager };
}

function at(state: string, persona: string, clock: string, editing: boolean): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          const manages = (who ?? persona) === "hannah-leclerc";
          return json({
            ...base,
            capabilities: manages ? [...base.capabilities, "sheet.configure"] : base.capabilities,
            flags: { ...base.flags, "sheets.enabled": true, "collaboration.v2": true },
          });
        },
        "GET /v1/sheets/{sheet_id}": () => json(vm(editing)),
        "GET /v1/sheets/{sheet_id}/rows": () => json({ items: rows("filled"), next_cursor: null }),
        "GET /v1/sheets/{sheet_id}/columns/{column_id}/usage": () =>
          json(
            editing
              ? exported.usage_in_use
              : {
                  filled_rows: 0,
                  views: 0,
                  view_names: [],
                  rules: 0,
                  agent_columns: [],
                  in_use: false,
                },
          ),
        "POST /v1/sheets/{sheet_id}/columns": () => json(SERVICE_PERIOD, 201),
        "PATCH /v1/sheets/{sheet_id}/columns/{column_id}": () => json(SERVICE_PERIOD),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "hannah-leclerc", "2026-09-24T11:20:00-05:00", false), // New
  b: at("b", "hannah-leclerc", "2026-09-24T11:20:00-05:00", false), // Type picker open
  c: at("c", "hannah-leclerc", "2026-09-30T09:50:00-05:00", true), // Edit
  d: at("d", "hannah-leclerc", "2026-09-30T09:50:00-05:00", true), // Type change warning
  e: at("e", "hannah-leclerc", "2026-09-30T09:50:00-05:00", true), // Blocked delete
  f: at("f", "simone-baptiste", "2026-09-24T11:20:00-05:00", false), // Not a manager
});

export type Sht02State = keyof typeof scenarios;

/** How each artboard opens the drawer: the column, and what is already open in it. */
export const INITIAL: Record<
  Sht02State,
  { columnId: string; afterKey?: string; initialType?: "text"; initialDelete?: boolean }
> = {
  a: { columnId: "new", afterKey: AFTER_KEY },
  b: { columnId: "new", afterKey: AFTER_KEY },
  c: { columnId: SERVICE_PERIOD.column_id },
  d: { columnId: SERVICE_PERIOD.column_id, initialType: "text" },
  e: { columnId: SERVICE_PERIOD.column_id, initialDelete: true },
  f: { columnId: "new", afterKey: AFTER_KEY },
};
