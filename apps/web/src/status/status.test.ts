// F-05-T12 (C2, C-06): status() over the generated registry. Every blueprint 3.3.1 and addendum 3.2
// row resolves, a context words a code differently where the registry says so, and every one of
// the 144 words in the handoff's lib/status.js is mapped to a registry code or retired.
import {
  HANDOFF_OBJECTS,
  HANDOFF_WORDS,
  RETIRED,
  RETIRED_CODES,
  STATUS,
  STATUS_REGISTRY,
  type RegistryCode,
  type RegistryContext,
  type RegistryObject,
  handoffStatus,
  status,
} from "@abacus/ui";
import { describe, expect, it } from "vitest";

interface Row {
  object: RegistryObject;
  code: string;
  entry: {
    label: string;
    variant: string | null;
    derived: boolean;
    terminal: boolean;
    disc?: string;
    clientLabel?: string;
    contextLabels?: Record<string, string>;
  };
}

const REGISTRY: Record<string, Record<string, Row["entry"]>> = STATUS_REGISTRY;
const ROWS: Row[] = Object.entries(REGISTRY).flatMap(([object, codes]) =>
  Object.entries(codes).map(([code, entry]) => ({
    object: object as RegistryObject,
    code,
    entry,
  })),
);

/** `status()` for a code held as a string, the way a test reads the registry. */
function resolve(
  object: string,
  code: string,
  options: Parameters<typeof status>[2] = {},
): ReturnType<typeof status> {
  return status(object as RegistryObject, code as RegistryCode<RegistryObject>, options);
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].flatMap((m) => (m[1] === undefined ? [] : [m[1]]));
}

describe("ac1 every blueprint 3.3.1 and addendum 3.2 row resolves", () => {
  it("holds every row of the registry", () => {
    // P-04-T02 added decision_card, suggestion, proposal, sign_off_slot and field_value.
    // P-07-T03 added client, invitation, acceptance_record, letter_record, conflict_assessment,
    // nas_evaluation and independence_conclusion (+7). P-03-T02 added citation, viewer and
    // evidence_unlock (+3). G-01-T02 added membership, wall_approval and annual_independence (+3).
    // Q-02-T30 added legal_hold (+1). A-01-T01 added engagement_export (+1).
    // A-02-T02 added trial_balance_label and trial_balance_layer (+2).
    // S9 to S12 added human_gate, due_risk, methodology_version, methodology_import,
    // knowledge_item, parse_flag, ai_policy_version, security_incident, firm_export,
    // firm_export_schedule, safeguards_control, support_session and client_invitation (+13).
    // S13 (N-01, N-02) and F-06-T03 added inbox_thread, portal_intake_upload, file_document,
    // envelope_signer, signing_step, envelope_purpose, generated_document, letter and
    // letter_clause (+9; the S14 batch joins N-02's and F-06's envelope_signer, DEC-815).
    // K-02-T02 added firm_standard_version and reference_set_version (+2).
    // T-01-T06 added tax_authorization and efile_ack (+2; the sync chip is the blueprint's
    // return_sync_chip). T-02-T04 added questionnaire, recipient_details_change, k1_handoff (+3).
    // The S16 end review added engine_import and transcript_parse (T-01) and k3 (T-02) (+3).
    expect(Object.keys(REGISTRY)).toHaveLength(110);
    // +21: decision_card 3, suggestion 6, proposal 5, sign_off_slot 2, field_value 4, checkpoint saved.
    // +27 (P-07-T03): client 4, invitation 5, acceptance_record 5, letter_record 2,
    // conflict_assessment 5, nas_evaluation 3, independence_conclusion 3.
    // +11 (P-03-T02): citation 4, viewer 5, evidence_unlock 2.
    // +8 (G-01-T02): membership 3, wall_approval 2, annual_independence 3.
    // +4 (Q-02-T30): legal_hold 4.
    // +6 (A-01-T01): engagement_export 6.
    // +9 (A-02-T02): trial_balance_label 5, trial_balance_layer 4.
    // +1 (P-07-T36): conflict_assessment `conflict`.
    // +53 (S9 to S12): human_gate 4, due_risk 4, methodology_version 6, methodology_import 6,
    // knowledge_item 3, parse_flag 5, ai_policy_version 6, security_incident 2, firm_export 4,
    // firm_export_schedule 3, safeguards_control 2, support_session 4, client_invitation 4.
    // +41 (S13, F-06-T03): inbox_thread 3, portal_intake_upload 3, file_document 5,
    // envelope_signer 6, signing_step 4, envelope_purpose 4, generated_document 4, letter 7,
    // letter_clause 3, inbox_item +2.
    // +8 (K-02-T02): firm_standard_version 4, reference_set_version 4.
    // +9 (T-01-T06): consent superseded and not_requested, tax_authorization 5, efile_ack 2.
    // +8 (T-02-T04): questionnaire 3, recipient_details_change 3, k1_handoff 2.
    // +11 (S16 end review): engine_import 5, transcript_parse 3 (T-01), k3 3 (T-02).
    expect(ROWS).toHaveLength(507);
  });

  it("resolves each code to a word, a kit variant or a line, and never to match", () => {
    for (const { object, code, entry } of ROWS) {
      const vars = Object.fromEntries(placeholders(entry.label).map((k) => [k, "X"]));
      const resolved = resolve(object, code, { vars });
      expect(resolved.unknown, `${object}.${code}`).toBe(false);
      expect(resolved.label.trim(), `${object}.${code}`).not.toBe("");
      expect(resolved.label, `${object}.${code}`).not.toContain("{");
      expect(resolved.derived).toBe(entry.derived);
      expect(resolved.terminal).toBe(entry.terminal);
      expect(resolved.variant).not.toBe("match");
      expect(resolved.variant === null, `${object}.${code}`).toBe(entry.variant === null);
      expect(resolved.mark, `${object}.${code}`).toBe(entry.disc ?? null);
    }
  });

  it("words a code in each context the registry names, and in the client's voice", () => {
    for (const { object, code, entry } of ROWS) {
      for (const [context, template] of Object.entries(entry.contextLabels ?? {})) {
        const vars = Object.fromEntries(placeholders(template).map((k) => [k, "X"]));
        const resolved = resolve(object, code, { context: context as RegistryContext, vars });
        expect(resolved.label, `${object}.${code} in ${context}`).toBe(
          template.replace(/\{(\w+)\}/g, "X"),
        );
      }
      if (entry.clientLabel !== undefined) {
        const resolved = resolve(object, code, { client: true });
        expect(resolved.label.startsWith(entry.clientLabel.replace(/\s*\{.*$/, ""))).toBe(true);
      }
    }
  });

  it("reads Return/preparing as Draft on a 1040 subbar and Working on entity returns", () => {
    expect(status("return", "preparing").label).toBe("Preparing");
    expect(status("return", "preparing", { context: "subbar_1040_1041" }).label).toBe("Draft");
    expect(status("return", "preparing", { context: "subbar_entity_returns" }).label).toBe(
      "Working",
    );
  });

  it("fills the placeholders it is given and drops the rest with their separator", () => {
    expect(
      status("return", "in_review", { context: "subbar_rail_rows", vars: { level: "Manager" } })
        .label,
    ).toBe("In review · Manager");
    const bare = status("return", "in_review", { context: "subbar_rail_rows" });
    expect(bare.label).toBe("In review");
    expect(bare.unfilled).toEqual(["level"]);
    expect(status("return_sync_chip", "synced", { vars: { date: "Sep 10" } }).label).toBe(
      "Synced Sep 10",
    );
    expect(status("request", "returned", { vars: { reason: "wrong year" } }).label).toBe(
      "Returned · wrong year",
    );
  });

  it("gives a context its own variant where the registry does", () => {
    expect(status("return", "prepared").variant).toBe("neutral");
    expect(status("return", "prepared", { context: "subbar" }).variant).toBe("amber");
  });

  it("reads an unknown code as itself in a neutral pill", () => {
    const unknown = resolve("request", "mystery");
    expect(unknown).toMatchObject({ label: "mystery", variant: "neutral", unknown: true });
  });
});

describe("c-06 how the registry is drawn", () => {
  it("draws the state variant as the amber tint", () => {
    expect(status("engagement", "active").variant).toBe("amber");
    expect(status("deficiency", "exception_for_resolution").variant).toBe("amber");
  });

  it("draws a registry disc as the kit's disc, with the line beside it", () => {
    expect(status("agent_run", "running")).toMatchObject({
      variant: null,
      disc: { state: "run", size: 15 },
      line: "text",
    });
    expect(status("close_task", "needs_attention").disc?.state).toBe("warn");
    expect(status("inbox_item", "new").disc).toEqual({ state: "todo", size: 16 });
    expect(status("inbox_item", "filed").disc).toEqual({ state: "done", size: 15 });
    expect(status("proposed_entry", "review_required").line).toBe("text-amber");
  });

  it("leaves the disc to the owning kit when C-06 draws none, and keeps the registry's name", () => {
    expect(status("issue", "open")).toMatchObject({ disc: null, mark: "flag" });
    expect(status("archive", "locked")).toMatchObject({ disc: null, mark: "lock" });
    expect(status("document", "approved")).toMatchObject({ disc: null, mark: "check_ink_micro" });
  });

  it("gives the sync chip a glyph, never a disc", () => {
    const glyphs = Object.keys(REGISTRY.return_sync_chip ?? {}).map(
      (code) => resolve("return_sync_chip", code).glyph,
    );
    expect(glyphs).toEqual(["refresh", "refresh", "spin", "synced", "out", "pending", "failed"]);
    expect(status("return_sync_chip", "synced").disc).toBeNull();
    expect(status("return_sync_chip", "ready_for_export", { context: "tile" }).label).toBe(
      "Ready",
    );
  });

  it("puts a check before a finished state, unless the word carries its own", () => {
    expect(status("engagement", "delivered")).toMatchObject({ variant: "green", check: true });
    expect(status("request", "received")).toMatchObject({ variant: "green", check: false });
    expect(status("tie_out_tally", "tie")).toMatchObject({ variant: "green", check: false });
    expect(status("engagement", "active").check).toBe(false);
  });

  it("marks a material weakness bold, and the sizes follow the object", () => {
    expect(status("deficiency_severity", "material_weakness").bold).toBe(true);
    expect(status("deficiency_severity", "significant_deficiency").bold).toBe(false);
    expect(status("close", "in_progress").size).toBe("status");
    expect(status("audit_engagement", "planning").size).toBe("card-state");
    expect(status("document", "matched").size).toBe("sm");
    expect(status("misstatement_type", "factual").size).toBe("tag");
    expect(status("integration", "available").size).toBe("outline");
    expect(status("integration", "coming_soon").size).toBe("sm");
    expect(status("tie_out_tally", "off", { vars: { amount: "8,500" } })).toMatchObject({
      size: "tally",
      label: "off 8,500",
    });
  });
});

describe("ac2 every word of the handoff's lib/status.js is mapped or retired", () => {
  const words = Object.entries(HANDOFF_OBJECTS).flatMap(([object, list]) =>
    list.map((word) => ({ object, word })),
  );

  it("has the 21 objects and 144 words of lib/status.js", () => {
    expect(Object.keys(HANDOFF_OBJECTS)).toHaveLength(21);
    expect(words).toHaveLength(144);
  });

  it("resolves each word to a registry code, or to its retirement and replacement", () => {
    let mapped = 0;
    let retired = 0;
    for (const { object, word } of words) {
      const result = handoffStatus(object, word);
      expect(result, `${object}.${word}`).not.toBeNull();
      if (result !== null && "mapped" in result) {
        mapped += 1;
        expect(result.mapped.unknown, `${object}.${word}`).toBe(false);
      } else if (result !== null) {
        retired += 1;
        expect(result.retired.reason.length, `${object}.${word}`).toBeGreaterThan(10);
        if (result.retired.replacement !== null) {
          const [obj = "", code = ""] = result.retired.replacement.split(".");
          expect(REGISTRY[obj]?.[code], `${object}.${word}`).toBeDefined();
        }
      }
    }
    expect(mapped + retired).toBe(144);
    expect(retired).toBe(Object.keys(RETIRED).length);
    expect({ mapped, retired }).toEqual({ mapped: 123, retired: 21 });
  });

  it("says where a word that changed meaning went", () => {
    const at = (object: string, word: string): string | undefined => {
      const result = handoffStatus(object, word);
      return result !== null && "mapped" in result
        ? `${result.mapped.object}.${result.mapped.code}`
        : undefined;
    };
    expect(at("Tax return", "Ready to file")).toBe("return.approved");
    expect(at("Tax return", "Working")).toBe("return.preparing");
    expect(at("Document", "Received")).toBe("request.uploaded");
    expect(at("Audit", "Ready to issue")).toBe("audit_engagement.ready_to_release");
    expect(at("Close", "Closed")).toBe("close.locked");
    expect(at("Tally", "Ties")).toBe("tie_out_tally.tie");
    expect(RETIRED["Request.Cancelled"]?.replacement).toBeNull();
    expect(RETIRED["Engagement.Draft"]?.replacement).toBe("engagement.prospect");
    expect(handoffStatus("Tax return", "Nope")).toBeNull();
    expect(handoffStatus("Nope", "Draft")).toBeNull();
  });

  it("agrees with the generated table", () => {
    const table: Record<string, Record<string, unknown>> = HANDOFF_WORDS;
    expect(Object.values(table).reduce((n, w) => n + Object.keys(w).length, 0)).toBe(144);
  });
});

describe("retired codes", () => {
  const retired: Record<string, { replacement: readonly string[] }> = RETIRED_CODES;

  it("name replacements that exist in the registry", () => {
    for (const [key, { replacement }] of Object.entries(retired)) {
      for (const target of replacement) {
        const [obj = "", code = ""] = target.split(".");
        expect(REGISTRY[obj]?.[code], `${key} -> ${target}`).toBeDefined();
      }
    }
  });

  it("confirm the legacy app codes: each ui.* entry is a code in STATUS", () => {
    const legacy: Record<string, Record<string, unknown>> = STATUS;
    const keys = Object.keys(retired).filter((k) => k.startsWith("ui."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      const [, domain = "", code = ""] = key.split(".");
      expect(legacy[domain]?.[code], key).toBeDefined();
    }
  });
});
