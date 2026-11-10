// SHL-18 a–f (P-05-T10): one scenario per artboard from the collaboration seed (P-05-T03). a, b,
// b2, c and e are live (the same data comes from the seed through the routes); d and f are
// gallery-only until their host epics (A-10's FSP-01 dock, A-09's POR-23 room) register the anchor.
import type { Scenario } from "../../app-core/fixture-mode";
import { defineScenarios } from "../../app-core/fixture-mode";
import { collaborationHandlers } from "../handlers/collaboration";
import { seedScenario } from "../scenario";
import { CLOCKS, IDS, P, PERSONAS, type Shl18State } from "../seed/collaboration";

const E0 = seedScenario();

function frame(state: Shl18State, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return { ...E0.handlers, ...collaborationHandlers({ shl18: state }) };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", PERSONAS.margaret, CLOCKS.shl18a),
  b: frame("b", PERSONAS.margaret, CLOCKS.shl18b),
  b2: frame("b2", PERSONAS.margaret, CLOCKS.shl18a),
  c: frame("c", PERSONAS.margaret, CLOCKS.shl18a),
  d: frame("d", PERSONAS.hannah, CLOCKS.shl18d),
  e: frame("e", PERSONAS.simone, CLOCKS.shl18e),
  f: frame("f", PERSONAS.omar, CLOCKS.shl18f),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];

export interface Shl18Frame {
  variant: "popover" | "dock" | "drawer";
  anchor: { anchor_kind: string; anchor_id: string; locator?: Record<string, string | number> };
  anchorLabel: string;
  engagementId: string;
  engagementLabel: string;
  viewerId: string;
  context?: { title: string; kind?: string };
  sharedWith?: string;
  draft?: string;
  live: boolean;
}

const row3 = {
  variant: "popover",
  anchor: {
    anchor_kind: "workpaper",
    anchor_id: IDS.exceptions,
    locator: { cell: "A3", sheet: "Exceptions" },
  },
  anchorLabel: "Exceptions!A3 · Northwind PY2025",
  engagementId: IDS.northwind,
  engagementLabel: "Northwind PY2025",
  viewerId: P.margaret.user_id,
  context: {
    title: "Year-end contribution cutoff not recorded",
    kind: "Exception for resolution",
  },
  live: true,
} as const satisfies Shl18Frame;

export const FRAMES: Record<State, Shl18Frame> = {
  a: row3,
  b: { ...row3, draft: "@Ha" },
  b2: { ...row3, draft: "@" },
  c: { ...row3, draft: "@Si" },
  d: {
    variant: "dock",
    anchor: { anchor_kind: "statement_line", anchor_id: IDS.cashFlows },
    anchorLabel: "Statement of cash flows › Dividends paid",
    engagementId: IDS.granite,
    engagementLabel: "Granite Peak FY2026",
    viewerId: P.hannah.user_id,
    live: false,
  },
  e: {
    variant: "drawer",
    anchor: {
      anchor_kind: "workpaper",
      anchor_id: IDS.exceptions,
      locator: { row: 3, sheet: "SURL-03" },
    },
    anchorLabel: "BH-FS-430 · SURL-03 · Mesa Packaging Supply · 57,250",
    engagementId: IDS.northwind,
    engagementLabel: "Northwind PY2025",
    viewerId: P.simone.user_id,
    live: true,
  },
  f: {
    variant: "popover",
    anchor: { anchor_kind: "component_thread", anchor_id: IDS.componentRoom },
    anchorLabel: "Pruett & Lang LLP",
    engagementId: IDS.harlow,
    engagementLabel: "Harlow & Pike FY2026",
    viewerId: P.omar.user_id,
    sharedWith: "Pruett & Lang LLP",
    live: false,
  },
};
