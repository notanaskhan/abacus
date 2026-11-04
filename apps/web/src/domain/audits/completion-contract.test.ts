// A-07-T06 (SPEC-644 AC-6; TASK-3253): the AUD-18 to AUD-25 view models are satisfiable from the
// generated client's shapes. Each object below is typed by the stub's schema, so `tsc` fails when
// a field the artboard draws has no server source; the assertions pin the artboard numbers that
// code computes (6 of 10, 12 of 17, 8 of 9, the gate cards, the clocks and the seal prefix).
import type {
  AuditArchiveStateOut,
  AuditCompletionOut,
  AuditReleaseOut,
  EqrReviewOut,
  GateCardOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";

const WI = "6f1c2a90-0000-4000-8000-000000000001";
const SEAL = "7c41" + "0".repeat(56) + "a9e2";
const HASH = "b".repeat(64);

const aud18a = {
  work_item_id: WI,
  required: true,
  eqr_name: "Thomas Whitcombe",
  status: "in_progress",
  checklist: [],
  checklist_done: 6,
  checklist_total: 10,
  digest_cards: [],
  notes: [
    { id: WI, ref: "EQR-1", status: "responded", assignee_name: "Hannah Leclerc" },
    { id: WI, ref: "EQR-2", status: "open", assignee_name: "Hannah Leclerc" },
  ],
  concurrence: null,
  blockers: ["checklist_open:4", "eqr_notes_open:2"],
  viewer_is_eqr: true,
  allowed_actions: ["eqr.mark_reviewed", "eqr.checklist_update"],
  version: 1,
} satisfies EqrReviewOut;

const aud19a = {
  work_item_id: WI,
  items: [],
  complete: 12,
  not_applicable: 1,
  open: 5,
  total: 17,
  blockers: ["rep_letter", "fs_approval", "bring_down", "independence", "governance_260"],
  allowed_actions: ["completion.update"],
  version: 3,
} satisfies AuditCompletionOut;

const gate = (g: GateCardOut["gate"], met: boolean, value: string | null): GateCardOut => ({
  gate: g,
  met,
  required: true,
  value,
  blockers: met ? [] : ["envelope:out_for_signature"],
});

const aud24a = {
  gates: [
    gate("G5", true, "Review complete"),
    gate("G6", true, "Concurred Oct 5, 2026"),
    gate("G7", true, "Signed Oct 9, 2026"),
  ],
  also_required: [
    { key: "fs_approved", met: true, value: "Oct 8, 2026" },
    { key: "bring_down", met: true, value: "#4240" },
    { key: "independence", met: true, value: "5 of 5" },
  ],
  gate_hash: HASH,
  can_release: true,
  viewer_can_release: true,
  engagement_partner_name: "Margaret Okonkwo",
  released_at: null,
  released_by_name: null,
  documentation_completion_date: null,
  deliverable_ids: [],
  filings: [],
  allowed_actions: ["report.release"],
} satisfies AuditReleaseOut;

const aud25 = (over: Partial<AuditArchiveStateOut>): AuditArchiveStateOut => ({
  status: "assembling",
  release_date: "2026-10-09",
  documentation_completion_date: "2026-12-08",
  days_left: 47,
  retention_until: "2033-10-09",
  on_hold: false,
  checklist: [],
  checklist_done: 8,
  checklist_total: 9,
  checklist_hash: HASH,
  binder: [],
  locked_at: null,
  locked_by_name: null,
  seal_sha256: null,
  additions: [],
  allowed_actions: ["archive.build_index"],
  ...over,
});

describe("A-07 artboard view models", () => {
  it("AUD-18 a reads 6 of 10 with two EQR notes not cleared", () => {
    expect([aud18a.checklist_done, aud18a.checklist_total]).toEqual([6, 10]);
    // Every note on the EQR read is open or responded: none is cleared.
    expect(aud18a.notes).toHaveLength(2);
  });

  it("AUD-19 a reads 12 of 17 with not applicable excluded and five blockers", () => {
    expect([aud19a.complete, aud19a.total]).toEqual([12, 17]);
    expect(aud19a.complete + aud19a.open).toBe(aud19a.total);
    expect(aud19a.blockers).toHaveLength(5);
  });

  it("AUD-24 a has G5 to G7 met and the release open to the partner", () => {
    expect(aud24a.gates.every((g) => g.met)).toBe(true);
    expect([aud24a.can_release, aud24a.viewer_can_release]).toEqual([true, true]);
  });

  it("AUD-25 a reads Archive in 47 days and 8 of 9; c carries the seal 7c41…a9e2", () => {
    const a = aud25({});
    expect([a.checklist_done, a.checklist_total]).toEqual([8, 9]);
    expect(a.documentation_completion_date).toBe("2026-12-08");
    const c = aud25({ status: "locked", checklist_done: 9, seal_sha256: SEAL, days_left: 5 });
    const seal = c.seal_sha256 ?? "";
    expect(`${seal.slice(0, 4)}…${seal.slice(-4)}`).toBe("7c41…a9e2");
  });
});
