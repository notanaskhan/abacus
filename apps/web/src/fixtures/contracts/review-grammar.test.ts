// P-04-T09: C3 v1 consumer fixture assertions for stubs 1 and 2. One typed frame per SHL-10 a–g,
// SHL-11 a–h and SHL-12 a–h artboard, built against the generated client's types (a removed or
// renamed field fails tsc) and checked against the OpenAPI document at run time (a field the schema
// no longer has fails here). Figures foot with bigint decimals, never floats. Copy and figures come
// from docs/contracts/review-grammar.md §8 and the P-04 epic's artboard rows; ids are placeholders.
// The UI tasks (P-04 S16–S24) build their scenarios from these shapes. P-04-T12 adds stub 3: one
// frame per SHL-09 a–f, SHL-15 a–e and SHL-16 a–f artboard, an additive extension of C3 v1.
// P-04-T34: every frame, request and answer lives in fixtures/seed/review.ts, which the fixture
// handlers serve; this file only asserts on them (no frame is drafted here).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";
import {
  ADOPTED_B,
  AJE05,
  APPROVE_A,
  APPROVE_EDITS_B,
  BATCH,
  BULK_E,
  BULK_F,
  BULK_OUT_E,
  CARD_PAGE_E,
  COMPARE_C,
  CP6_HASH,
  DANA,
  DECIDE_A,
  DECIDE_F,
  EDIT_C,
  EXPLAIN_ACCEPTED_D,
  FELD_1040,
  FIELD_V2,
  FIX_A,
  FIX_ACCEPTED_A,
  FLAG_C,
  INSTRUCTIONS,
  ISSUES_FIVE,
  ISSUES_FOUR,
  KEVIN,
  NOTE,
  NOTE_DETAIL,
  PRIYA,
  PROVENANCE,
  REFERENCE_E,
  REJECT_E,
  REJECT_F,
  RENAME_D,
  RESTORE_C,
  ROUTE_D,
  SAMUEL,
  SAVE_F,
  SEND_B,
  SEVEN,
  SHL09,
  SHL10,
  SHL11,
  SHL12,
  SHL15,
  SHL16,
  SIGN_A_PRIME,
  STALE_LADDER,
  STATEMENT,
  TB,
  TICK_A,
  WORDING,
  cards,
  cp6,
  cp6Detail,
  decision,
  dollars,
  hannahL2,
  k1,
  marcusL1,
  milli,
  notes,
  optOuts,
  roundTo,
  sum,
  target,
  times,
} from "../seed/review";

// --- Helpers ---------------------------------------------------------------------------------

const here = dirname(fileURLToPath(import.meta.url));
const SCHEMAS = (
  JSON.parse(
    readFileSync(
      join(here, "..", "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
      "utf8",
    ),
  ) as {
    components: { schemas: Record<string, { properties?: Record<string, { cls?: string }> }> };
  }
).components.schemas;

/** A field's classification tag in the OpenAPI document (ADR-031). */
function cls(schema: string, field: string): string | undefined {
  return SCHEMAS[schema]?.properties?.[field]?.cls;
}

/** A stable placeholder uuid (v4 shape) for frame `n`. */

describe("SHL-12 a–h (stub 1)", () => {
  it("every eligibility frame is the GET /v1/sign-offs/eligibility shape", () => {
    for (const [key, frame] of Object.entries(SHL12)) {
      expect(validateResponse("GET", "/v1/sign-offs/eligibility", frame), key).toEqual([]);
    }
  });

  it("a: every value cited, 14 of 14 cells; the L1 is agent run #4127 adopted by MD", () => {
    const cited = SHL12.a.checks.find((c) => c.code === "all_cited");
    expect(cited?.facts).toEqual({ cited: 14, cells: 14 });
    expect(cited?.facts.cited).toBe(SHL12.a.target.cell_count);
    expect(SHL12.a.ladder[0]?.latest?.adopted_run_number).toBe(4127);
    expect(SHL12.a.checks.find((c) => c.code === "gate_g4")?.result).toBe("warn");
  });

  it("a′: sign with the full digest seen; the 201 is one row; the header reads ✓ MD ✓ HL", () => {
    const body = SIGN_A_PRIME;
    expect(validateSchema("SignOffIn", body)).toEqual([]);
    expect([body.target_id, body.statement_version]).toEqual([TB, STATEMENT]);
    expect(body.seen_hash).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(validateSchema("SignOffOut", hannahL2)).toEqual([]);
    expect([marcusL1, hannahL2].map((s) => `✓ ${s.initials}`).join(" ")).toBe("✓ MD ✓ HL");
  });

  it("b: two open notes on RA!C14 and RA!C22; list rows carry no sealed body", () => {
    expect(validateResponse("GET", "/v1/review-notes", notes)).toEqual([]);
    expect(notes.items.map((n) => n.anchor?.ref)).toEqual(["RA!C14", "RA!C22"]);
    expect(notes.counts).toEqual({ open: notes.total });
    expect(notes.items.every((n) => !("body" in n))).toBe(true);
    expect(NOTE_DETAIL.note).toBe(notes.items[0]);
    expect(validateResponse("GET", "/v1/review-notes/{note_id}", NOTE_DETAIL)).toEqual([]);
    expect(cls("ReviewNoteDetailOut", "body")).toBe("restricted");
    expect(cls("ReviewNoteEventOut", "body")).toBe("restricted");
  });

  it("c, d: the same preparer and a missing independence confirmation block", () => {
    expect(SHL12.c.checks.find((c) => c.code === "segregation")?.result).toBe("fail");
    expect(SHL12.d.checks.find((c) => c.code === "independence")?.result).toBe("fail");
  });

  it("e: a later change makes the L2 stale; staleness is computed, the ladder only re-signs", () => {
    const frame = STALE_LADDER;
    expect(validateResponse("GET", "/v1/sign-offs", frame)).toEqual([]);
    expect(frame.target.content_hash).not.toBe(target.content_hash);
    expect(frame.levels[1]?.latest?.stale).toBe(true);
    expect(sum([milli("16,812,400"), milli("48,600")])).toBe(milli("16,861,000"));
  });

  it("f: six selected, three signed and three excluded with their reasons", () => {
    const frame = BULK_F;
    expect(validateResponse("POST", "/v1/sign-offs:bulk", frame)).toEqual([]);
    expect(frame.results.filter((r) => !r.ok).map((r) => r.detail)).toEqual([
      "incomplete",
      "open_review_notes",
      "segregation",
    ]);
    expect(frame.signed + frame.excluded).toBe(frame.results.length);
  });

  it("g: the EQR sees only L5; h: final approval waits on 11 open issues", () => {
    expect(SHL12.g.levels_allowed).toEqual(["L5_eqr"]);
    expect(SHL12.h.checks[0]?.facts.count).toBe(11);
    expect(SHL12.h.eligible).toBe(false);
  });
});

describe("SHL-11 a–h (stub 2)", () => {
  it("every card frame is the GET /v1/decision-cards/{card_id} shape", () => {
    for (const [key, frame] of Object.entries(SHL11)) {
      expect(validateResponse("GET", "/v1/decision-cards/{card_id}", frame), key).toEqual([]);
    }
  });

  it("a: the options foot in code (168,100; 252,200 · PM 189,150 · CT 12,610)", () => {
    const amount = milli(SHL11.a.context.find((c) => c.key === "amount")?.value ?? "0");
    for (const o of SHL11.a.options) {
      const f = o.figures;
      const m = milli(f.materiality ?? "");
      expect(roundTo(times(milli(f.rate ?? ""), amount), milli("100")), o.key).toBe(m);
      expect(times(m, milli("0.75"))).toBe(milli(f.performance_materiality ?? ""));
      expect(times(m, milli("0.05"))).toBe(milli(f.clearly_trivial ?? ""));
      expect(o.label).toContain(dollars(m));
    }
    expect(SHL11.a.options.filter((o) => o.recommended).map((o) => o.key)).toEqual([
      SHL11.a.recommendation?.option_key,
    ]);
  });

  it("a–c: the reserved role decides with a sealed rationale; the card stamps v2", () => {
    const body = DECIDE_A;
    expect(validateSchema("CardDecideIn", body)).toEqual([]);
    expect(body.rationale).toBe(decision.rationale);
    expect(validateResponse("POST", "/v1/decision-cards/{card_id}/decide", SHL11.c)).toEqual([]);
    expect(cls("CardDecisionOut", "rationale")).toBe("restricted");
    expect(cls("DecisionCardOut", "decision")).toBe("restricted");
    const f = SHL11.c.options.find((o) => o.key === SHL11.c.decision?.option_key)?.figures ?? {};
    const [m, pm, ct] = ["materiality", "performance_materiality", "clearly_trivial"].map((k) =>
      dollars(milli(f[k] ?? "0")),
    );
    expect(
      `v${String(SHL11.c.card.version_no)}: 1.5% = ${m ?? ""} · PM ${pm ?? ""} · CT ${ct ?? ""}`,
    ).toBe("v2: 1.5% = $252,200 · PM $189,150 · CT $12,610");
  });

  it("b: outside the reserved role there is Notify and Request more analysis, no Decide", () => {
    expect(SHL11.b.card.allowed_actions).not.toContain("decision.decide");
    expect(SHL11.b.card.reserved_user_name).toBe("Margaret Okonkwo");
  });

  it("d: reassessed at final on $16,861,000: 252,900, a $700 difference, no change", () => {
    const v3 = SHL11.d.history[2];
    const benchmark = milli(v3?.figures.benchmark ?? "");
    expect(benchmark).toBe(sum([milli("16,812,400"), milli("48,600")]));
    const m = roundTo(times(milli("0.015"), benchmark), milli("100"));
    expect(m).toBe(milli(v3?.figures.materiality ?? ""));
    expect(m - milli("252,200")).toBe(milli(v3?.figures.difference ?? ""));
    expect(v3?.changed).toBe(false);
  });

  it("e: the inline dock card reads the list row", () => {
    expect(validateResponse("GET", "/v1/decision-cards", CARD_PAGE_E)).toEqual([]);
    expect(CARD_PAGE_E.items).toEqual([SHL11.a.card]);
  });

  it("f: a rationale-less decide still parses; the service answers 422 rationale_required", () => {
    expect(validateSchema("CardDecideIn", DECIDE_F)).toEqual([]);
    expect(DECIDE_F.rationale).toBeUndefined();
  });

  it("g, h: §754 reserved to the signer; a superseded card points at its successor", () => {
    expect(SHL11.g.card.reserved_role).toBe("signer");
    expect(SHL11.h.card.superseded_by_version).toBe(3);
  });
});

describe("SHL-10 a–g (stub 2)", () => {
  it("every proposal frame is the GET /v1/proposals/{ref} shape", () => {
    for (const [key, frame] of Object.entries(SHL10)) {
      expect(validateResponse("GET", "/v1/proposals/{ref}", frame), key).toEqual([]);
    }
  });

  it("a: the net change to Form 1040 total income ties at 0; values are sealed", () => {
    const lines = SHL10.a.rows.filter((r) => r.field_key.startsWith("sch_e."));
    const net = sum(lines.map((r) => milli(r.after ?? "0") - milli(r.before ?? "0")));
    expect(net).toBe(milli(SHL10.a.totals[0]?.value ?? ""));
    expect(net).toBe(0n);
    expect(SHL10.a.totals[0]?.ties).toBe(true);
    expect(SHL10.a.change_count).toBe(SHL10.a.rows.length);
    const schema = "AgentProposalOut";
    for (const field of ["reasoning", "rows", "totals", "policy", "decision"]) {
      expect(cls(schema, field), field).toBe("restricted");
    }
    expect([cls("ProposalRowOut", "before"), cls("ProposalRowOut", "after")]).toEqual([
      "restricted",
      "restricted",
    ]);
  });

  it("b: approve with edits needs a citation note; one suggestion adopts line 2a", () => {
    expect(validateSchema("ApproveProposalIn", APPROVE_EDITS_B)).toEqual([]);
    expect(APPROVE_EDITS_B.edits?.every((e) => e.citation_note.length > 0)).toBe(true);
    const adopted = ADOPTED_B;
    expect(adopted.decided_by_user_id).toBe(SAMUEL);
    expect(validateResponse("POST", "/v1/suggestions/{suggestion_id}/adopt", adopted)).toEqual([]);
    expect(milli(adopted.proposed_value)).toBe(milli("1,550"));
    expect(cls("AgentSuggestionOut", "proposed_value")).toBe("restricted");
  });

  it("c: the uncited row blocks approval and Ask follow-up leads", () => {
    const uncited = SHL10.c.rows.filter((r) => r.unsupported);
    expect(uncited.map((r) => [r.n, r.citation_ids.length])).toEqual([[5, 0]]);
    expect(SHL10.c.allowed_actions).not.toContain("proposal.approve");
  });

  it("d: AJE-05 14,900.00 is over $10,000 and routes to Priya Raman", () => {
    const total = sum(AJE05.map(milli));
    expect(total).toBe(milli(SHL10.d.totals[0]?.value ?? ""));
    expect(total > milli("10,000")).toBe(true);
    expect(SHL10.d.policy.routed_to_name).toBe("Priya Raman");
    expect(validateSchema("RouteProposalIn", ROUTE_D)).toEqual([]);
    expect(ROUTE_D.approver_user_id).toBe(PRIYA);
  });

  it("e, e′: the within-threshold batch is approved by a named person with a 10 s Undo", () => {
    expect(milli(SHL10.e.totals[0]?.value ?? "")).toBe(milli(BATCH));
    expect([SHL10.e.state, SHL10.e.decision]).toEqual(["pending", null]);
    expect(milli(SHL10.e_prime.totals[0]?.value ?? "")).toBe(milli(BATCH));
    const d = SHL10.e_prime.decision;
    expect(d.decided_by_name).toBe("Raj Malhotra");
    expect(Date.parse(d.undo_until) - Date.parse(d.decided_at)).toBe(10_000);
  });

  it("f: reject with Needs client input", () => {
    expect(validateSchema("RejectProposalIn", REJECT_F)).toEqual([]);
    expect(REJECT_F.reason_code).toBe(SHL10.f.decision.reason_code);
    expect(validateResponse("POST", "/v1/proposals/{proposal_id}/reject", SHL10.f)).toEqual([]);
    expect(SHL10.f.decision.reason_code).toBe("needs_client_input");
  });

  it("g: the set link row: 40 results, 1 exception", () => {
    expect(SHL10.g.set).toMatchObject({ results: 40, exceptions: 1 });
  });
});

describe("SHL-09 a–f (stub 3)", () => {
  it("every frame is the GET …/provenance shape", () => {
    for (const [key, frame] of Object.entries(SHL09)) {
      expect(validateResponse("GET", PROVENANCE, frame), key).toEqual([]);
    }
  });

  it("a: 2,190 → 2,310 from the corrected 1099-INT; Kevin's earlier tick is stale", () => {
    const [now, before] = SHL09.a.versions;
    expect([milli(before?.value.v ?? ""), milli(now?.value.v ?? "")]).toEqual([
      milli("2,190"),
      milli("2,310"),
    ]);
    const box1 = now?.references.find((r) => r.kind === "document")?.detail ?? "";
    expect(milli(box1.split(": ")[1] ?? "")).toBe(milli("2,310"));
    expect(SHL09.a.ticks[0]?.stale).toBe(SHL09.a.ticks[0]?.content_hash !== SHL09.a.content_hash);
    expect(`${String(SHL09.a.versions.length)} versions`).toBe("2 versions");
    for (const field of ["versions", "flags"]) {
      expect(cls("FieldProvenanceOut", field), field).toBe("restricted");
    }
    expect([cls("FieldValueOut", "v"), cls("FieldVersionOut", "citation")]).toEqual([
      "restricted",
      "restricted",
    ]);
    expect(validateSchema("FieldTickIn", TICK_A)).toEqual([]);
    expect(TICK_A.seen_hash).toBe(FIELD_V2);
  });

  it("b: ≈ 48,000 is four vouchers of 12,000 and links its open issue", () => {
    const [estimate] = SHL09.b.versions;
    expect(estimate?.value_kind).toBe("estimate");
    expect(milli(estimate?.value.v ?? "")).toBe(4n * milli("12,000"));
    expect(estimate?.issue_id).not.toBeNull();
  });

  it("c: a person's edit carries its citation note", () => {
    const edit = EDIT_C;
    expect(validateSchema("FieldEditIn", edit)).toEqual([]);
    expect(validateSchema("FieldEditIn", { ...edit, citation_note: undefined })).not.toEqual([]);
    expect(SHL09.c.versions[0]?.actor_name).toBe("Kevin Osei");
  });

  it("d: both ticks are on the current hash", () => {
    expect(SHL09.d.ticks.map((t) => [t.initials, t.stale])).toEqual([
      ["KO", false],
      ["SI", false],
    ]);
  });

  it("e: an uncited agent value is Unsupported and cannot be ticked", () => {
    expect(SHL09.e.versions[0]?.unsupported).toBe(true);
    expect(SHL09.e.allowed_actions).not.toContain("field.sign_off");
    expect(validateSchema("FieldReferenceIn", REFERENCE_E)).toEqual([]);
  });
});

describe("SHL-16 a–f (stub 3)", () => {
  it("every history frame is the GET /v1/checkpoints shape", () => {
    for (const [key, frame] of Object.entries(SHL16)) {
      expect(validateResponse("GET", "/v1/checkpoints", frame), key).toEqual([]);
    }
    expect(validateResponse("GET", "/v1/checkpoints/{checkpoint_id}", cp6Detail)).toEqual([]);
  });

  it("a: Checkpoint 6 is the SHL-10 a proposal; the net change to total income ties at 0", () => {
    expect(cp6Detail.checkpoint.proposal_id).toBe(k1.ref);
    expect(cp6Detail.diff.map((r) => [r.field_key, r.old, r.new])).toEqual(
      k1.rows.map((r) => [r.field_key, r.before, r.after]),
    );
    const income = cp6Detail.diff.filter((r) => r.field_key.startsWith("sch_e."));
    const net = sum(income.map((r) => milli(r.new ?? "0") - milli(r.old ?? "0")));
    expect(net).toBe(milli(cp6Detail.totals[0]?.value ?? ""));
    expect(net).toBe(0n);
    expect(SHL16.a.items.filter((c) => c.current).map((c) => c.seq)).toEqual([5]);
    for (const field of ["summary", "decision"]) {
      expect(cls("CheckpointItemOut", field), field).toBe("restricted");
    }
    expect(validateSchema("CheckpointApproveIn", APPROVE_A)).toEqual([]);
    expect(APPROVE_A.seen_hash).toBe(CP6_HASH);
  });

  it("b: approving moves Current to Checkpoint 6", () => {
    const current = SHL16.b.items.filter((c) => c.current);
    expect(current.map((c) => c.seq)).toEqual([6]);
    expect(SHL16.b.current_checkpoint_id).toBe(cp6.id);
    expect(current[0]?.decision?.decided_by_name).toBe("Samuel Ito");
  });

  it("c: restoring Checkpoint 3 creates Checkpoint 7 as a copy", () => {
    const three = cards.find((c) => c.seq === 3);
    expect(validateSchema("CheckpointItemOut", SEVEN)).toEqual([]);
    expect([SEVEN.seq, SEVEN.cause, SEVEN.restored_from_id]).toEqual([7, "restore", three?.id]);
    expect(validateSchema("CheckpointRestoreIn", RESTORE_C)).toEqual([]);
    expect(RESTORE_C.seen_hash).toBe(three?.content_hash);
    expect(validateResponse("GET", "/v1/checkpoints/{checkpoint_id}", COMPARE_C)).toEqual([]);
    expect(COMPARE_C.compare).toBe("current");
  });

  it("d: rename and star change only name and starred", () => {
    expect(validateSchema("CheckpointRenameIn", RENAME_D)).toEqual([]);
    expect(SHL16.d.items.find((c) => c.seq === 5)).toMatchObject(RENAME_D);
  });

  it("e: rejected with a reason", () => {
    expect(validateSchema("CheckpointRejectIn", REJECT_E)).toEqual([]);
    const d = SHL16.e.items[0]?.decision;
    expect(`${d?.decided_by_name ?? ""} · reason: ${d?.reason ?? ""}`).toBe(
      "Samuel Ito · reason: Wait for final K-1",
    );
  });

  it("f: an empty return offers Save checkpoint…", () => {
    expect([SHL16.f.total, SHL16.f.items.length, SHL16.f.current_checkpoint_id]).toEqual([
      0,
      0,
      null,
    ]);
    expect(SHL16.f.allowed_actions).toEqual(["checkpoint.create"]);
    expect(validateSchema("CheckpointCreateIn", SAVE_F)).toEqual([]);
    expect(SAVE_F.target_id).toBe(SHL16.f.target_id);
  });
});

describe("SHL-15 a–e (stub 3)", () => {
  it("every issue frame is the GET /v1/issues/{issue_id} shape", () => {
    for (const [key, frame] of Object.entries(SHL15)) {
      expect(validateResponse("GET", "/v1/issues/{issue_id}", frame), key).toEqual([]);
    }
    expect(validateResponse("GET", "/v1/issues", ISSUES_FOUR)).toEqual([]);
  });

  it("a: Use suggestion plus one constraint; runs always propose", () => {
    const body = FIX_A;
    expect(validateSchema("FixInstructionsIn", body)).toEqual([]);
    expect(body.text).toBe(INSTRUCTIONS);
    expect(body.text.split("\n")[0]).toBe(SHL15.a.suggestion?.text);
    expect(validateSchema("FixInstructionsAcceptedOut", FIX_ACCEPTED_A)).toEqual([]);
    for (const field of ["title", "suggestion", "fix_instructions", "fix_run", "explanations"]) {
      expect(cls("IssueDetailOut", field), field).toBe("restricted");
    }
    expect(cls("IssueItemOut", "title")).toBeUndefined();
  });

  it("a′, a″: the run adds the same 1,550 the line 2a suggestion adopts, then proposes", () => {
    const amount = /(\d{1,3}(?:,\d{3})+)/.exec(SHL15.a_prime.fix_run?.label ?? "")?.[1] ?? "";
    expect(milli(amount)).toBe(milli("1,550"));
    expect(SHL15.a_prime.issue.status).toBe("in_progress");
    expect(SHL15.a_double_prime.fix_run.proposal_id).toBe(k1.ref);
  });

  it("b: four cells, four participants; only the client wording goes to the client", () => {
    expect(validateSchema("IssueCreateIn", optOuts)).toEqual([]);
    const [, first, last] =
      /^[A-Z]+(\d+):[A-Z]+(\d+)$/.exec(optOuts.links?.[0]?.anchor ?? "") ?? [];
    expect(Number(last) - Number(first) + 1).toBe(4);
    for (const word of ["EPCRS", "QACA", "QNEC", "AUD-15"]) {
      expect(NOTE, word).toContain(word);
      expect(WORDING, word).not.toContain(word);
    }
    expect(validateSchema("IssueSendToClientIn", SEND_B)).toEqual([]);
    expect([SEND_B.client_wording, SEND_B.contact_id]).toEqual([WORDING, DANA]);
    expect(SHL15.b.request_item_id).not.toBeNull();
  });

  it("c: a field flag raises a Review point; Feld Issues 4 → 5", () => {
    const flag = FLAG_C;
    expect([flag.record_id, flag.assignee_user_id]).toEqual([FELD_1040, KEVIN]);
    expect(validateSchema("IssueCreateIn", flag)).toEqual([]);
    expect(validateSchema("IssueCreateIn", { ...flag, kind: "urgent" })).not.toEqual([]);
    expect([ISSUES_FOUR.total, ISSUES_FIVE.total]).toEqual([4, 5]);
    expect(ISSUES_FIVE.items.length).toBe(ISSUES_FIVE.total);
    expect(validateResponse("GET", "/v1/issues", ISSUES_FIVE)).toEqual([]);
  });

  it("d: Explain is read-only agent text with three citations", () => {
    const [explanation] = SHL15.d.explanations;
    expect(explanation?.citations.map((c) => c.label)).toEqual([
      "K-1 box 18A",
      "K-1 statement p. 3",
      "IT-201 instructions, line 20",
    ]);
    expect(validateSchema("ExplainAcceptedOut", EXPLAIN_ACCEPTED_D)).toEqual([]);
  });

  it("e: bulk instructions for the 2 Missing information issues", () => {
    const bulk = BULK_E;
    expect(validateSchema("BulkFixInstructionsIn", bulk)).toEqual([]);
    const out = BULK_OUT_E;
    expect(validateSchema("BulkFixInstructionsOut", out)).toEqual([]);
    expect(out.accepted + out.excluded).toBe(out.results.length);
    expect(`Set Fix Instructions for ${String(bulk.issues.length)}`).toBe(
      "Set Fix Instructions for 2",
    );
  });
});
