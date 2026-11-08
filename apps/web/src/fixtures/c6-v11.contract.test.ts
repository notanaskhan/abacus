// P-09-T02 (TASK-6220; SPEC-648; docs/contracts/agent-runs.md §10): C6 v1.1's consumer side. Every
// field the SHL-13 dock and the WB-09 drawer read is present on each E0 fixture run, so each view
// model is satisfiable from the stub's shapes. `tsc` holds the types (the fixtures are typed by
// the generated client); this holds the presence, and fails when a field the surfaces read is
// dropped from a fixture or the client.
import { describe, expect, it } from "vitest";
import { E0_RUNS } from "./seed/agent-runs";

const DOCK = {
  run: ["id", "agent", "agent_label", "state", "started_at", "duration_ms", "initiator_name"],
  item: ["seq", "kind", "at", "code", "outcome", "detail", "actor", "session_kind"],
  view: ["run", "header", "levels", "access"],
} as const;

const DRAWER = {
  trace: ["run", "rows", "records_read", "summary", "access", "region", "runtime", "training"],
  row: ["seq", "at", "title", "state", "actor", "detail", "phase", "mark", "duration_ms"],
  read: ["source", "count", "connection_id", "through"],
  write: ["id", "key", "kind", "at", "decision", "state", "approver_name", "proposal_id"],
} as const;

function has(record: object, fields: readonly string[]): string[] {
  return fields.filter((f) => !(f in record));
}

describe("C6 v1.1 consumers (SHL-13 dock, WB-09 drawer)", () => {
  const runs = Object.entries(E0_RUNS);

  it("has the four E0 runs", () => {
    expect(runs.length).toBe(4);
  });

  for (const [id, run] of runs) {
    it(`dock: ${id} carries every field the dock reads`, () => {
      expect(has(run.view.run, DOCK.run)).toEqual([]);
      expect(has(run.view, DOCK.view)).toEqual([]);
      for (const item of run.items) expect(has(item, DOCK.item)).toEqual([]);
    });

    it(`drawer: ${id} carries every field the drawer reads`, () => {
      expect(has(run.trace, DRAWER.trace)).toEqual([]);
      for (const row of run.trace.rows) expect(has(row, DRAWER.row)).toEqual([]);
      for (const read of run.recordsRead) expect(has(read, DRAWER.read)).toEqual([]);
      for (const write of run.writes) expect(has(write, DRAWER.write)).toEqual([]);
    });

    it(`drawer: ${id}'s summary foots its own rows`, () => {
      const summary = run.trace.summary;
      if (summary == null) return;
      expect(summary.agent_label).toBe(run.view.run.agent_label);
      expect(summary.records_read).toBe(run.recordsRead.reduce((n, r) => n + r.count, 0));
    });
  }
});
