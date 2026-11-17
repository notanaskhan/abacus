// T-06-T09 (DEC-5518): consumer fixtures for the T-06 entity-depth and relationships stubs
// (docs/contracts/{tax-entity-depth,form-pages,relationships}.md; SPEC-702). Typed with the
// generated client and validated against the OpenAPI document; Ridgeline's 2025 figures foot.
// The pytest half is backend/tests/contracts/t06_entity_depth/.
import type {
  RelationshipGraphOut,
  TaxDepthK1PreviewsOut,
  TaxDepthStatesOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";

const R = "/v1/tax-returns/{return_id}";
const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const whole = (s: string): number => Math.round(Number(s) * 10);

const states: TaxDepthStatesOut = {
  view: "apportionment",
  states: [
    {
      state: "IL",
      apportionment_pct: "46.0",
      ptet: "elected",
      ptet_paid: "28044",
      ptet_paid_on: "2026-03-12",
      mapped: true,
    },
    {
      state: "CO",
      apportionment_pct: "31.5",
      ptet: "elected",
      ptet_paid: "17070",
      ptet_paid_on: "2026-03-12",
      mapped: true,
    },
    {
      state: "NY",
      apportionment_pct: "22.5",
      ptet: "elected",
      ptet_paid: "18982",
      ptet_paid_on: "2026-03-12",
      mapped: true,
    },
  ],
  apportionment_tally: "tie",
  sourcing: "proposed",
  paid_count: 3,
  payable_count: 3,
};

const k1: TaxDepthK1PreviewsOut = {
  items: [
    ["Ridgeline GP LLC", "24632"],
    ["Meera Shah", "468008"],
    ["Pell Street Ventures LLC", "400270"],
    ["Pell Street II LLC", "30790"],
    ["Jonah Feld", "307900"],
  ].map(([name, box2], i) => ({ partner_id: id(i + 1), name: name!, box_2: box2! })),
  box_2_total: "1231600",
  schedule_k_line_2: "1231600",
  tally: "tie",
};

const walledGraph: RelationshipGraphOut = {
  client_id: id(100),
  nodes: [
    {
      node_id: id(101),
      kind: "entity",
      label: "Ridgeline Property Partners, LP",
      external: false,
    },
  ],
  edges: [],
};

describe("T-06 stub fixtures", () => {
  it("TXP-09: 46.0 + 31.5 + 22.5 = 100.0 and PTET 64,096", () => {
    expect(states.states.reduce((t, s) => t + whole(s.apportionment_pct), 0)).toBe(1000);
    expect(states.states.reduce((t, s) => t + Number(s.ptet_paid), 0)).toBe(64096);
    expect(validateResponse("GET", `${R}/states`, states)).toEqual([]);
  });

  it("TAX-11 c: the K-1 list's box 2 sums to Schedule K line 2", () => {
    expect(k1.items.reduce((t, r) => t + Number(r.box_2), 0)).toBe(Number(k1.schedule_k_line_2));
    expect(validateResponse("GET", `${R}/k1-previews`, k1)).toEqual([]);
  });

  it("CLI-03: a walled view carries no count of what it hides", () => {
    expect(
      validateResponse("GET", "/v1/clients/{client_id}/relationship-graph", walledGraph),
    ).toEqual([]);
    expect(JSON.stringify(walledGraph)).not.toMatch(/hidden|walled/i);
  });
});
