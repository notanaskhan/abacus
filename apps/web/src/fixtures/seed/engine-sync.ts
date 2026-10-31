// TAX-09's engine-sync states (T-01-T15; docs/screens/TAX-09.md; the handoff spec): the Feld
// 2025 Form 1040 through the file bridge (CCH Axcess, never an API), one EngineSyncOut per
// artboard, and the V3 import diff. Figures are T-01-T09's (seed/tax-compliance.ts): 1.10 ×
// 123,223 = 135,545 − 55,585 = 79,960 ÷ 4 = 19,990; 141,634 + 96,989 + 69,277 = 307,900.
import type { EngineImportOut, EngineSyncEventOut, EngineSyncOut } from "@abacus/api-client";
import { count } from "@abacus/ui";
import { stableId } from "./prng";
import {
  FELD_ESTIMATE,
  FELD_RETURN_ID,
  FELD_STATE_INCOME,
  FELD_STATE_TOTAL,
} from "./tax-compliance";

const V3 = "2025I:FeldJ:V3";
const V2 = "2025I:FeldJ:V2";

function event(
  key: string,
  kind: EngineSyncEventOut["kind"],
  at: string,
  extra: Partial<EngineSyncEventOut> = {},
): EngineSyncEventOut {
  return {
    id: stableId(`engine-sync-event:feld:${key}`),
    kind,
    actor_name: "Samuel Ito",
    at,
    engine_version: null,
    field_keys: [],
    errors: null,
    informational: null,
    ...extra,
  };
}

const IMPORTED_V3 = event("import-v3", "import_approved", "2026-09-10T09:30:00-05:00", {
  engine_version: V3,
});
const IMPORTED_V2 = event("import-v2", "import_approved", "2026-04-14T10:00:00-05:00", {
  engine_version: V2,
});
const EXPORTED = event("export-v3", "marked_exported", "2026-09-16T11:44:00-05:00", {
  engine_version: V3,
});

const BASE: EngineSyncOut = {
  return_id: FELD_RETURN_ID,
  state: "ready_for_export",
  engine_return_id: V3,
  mode: "file_bridge",
  history: [IMPORTED_V3, IMPORTED_V2],
  diagnostics: [],
  allowed_actions: ["tax_return.read", "tax_return.export", "engine_import.create"],
  blockers: [],
  approver_name: "Daniel Reyes",
  policy_code: "BH-TAX-02",
  draft_k1_source: null,
  synced_at: null,
  // T-01-T33: the checkpoint Export generates from (the live read names the current one).
  checkpoint_id: stableId("checkpoint:feld-2025-final-approval"),
};

const INFORMATIONAL = [
  {
    code: "8995A_UBIA_STATEMENT_A",
    severity: "informational",
    field_key: "f8995a.ubia",
    message_text: "Form 8995-A — UBIA from Statement A used for the W-2/UBIA limit",
    issue_id: null,
  },
  {
    code: "IT201_L20_OTHER_STATE_INTEREST",
    severity: "informational",
    field_key: "it201.l20",
    message_text: "IT-201 line 20 — interest on other states' obligations 1,550 (source attached)",
    issue_id: null,
  },
] as const satisfies EngineSyncOut["diagnostics"];

/** One EngineSyncOut per TAX-09 artboard, plus the two non-artboard chip states. */
export const ENGINE_SYNC: Readonly<Record<string, EngineSyncOut>> = {
  // a2 (11:20 AM, just approved) and a (the export motion from it).
  a: BASE,
  a2: BASE,
  // b (Mon Sep 14): synced Sep 10; Export closed until final approval, a draft Ridgeline K-1.
  b: {
    ...BASE,
    state: "synced",
    synced_at: "2026-09-10T09:30:00-05:00",
    allowed_actions: ["tax_return.read", "engine_import.create"],
    blockers: [
      { kind: "final_approval_required", ref_id: null },
      { kind: "draft_k1", ref_id: stableId("k1-package:ridgeline-2025") },
    ],
    draft_k1_source: "Ridgeline",
  },
  // c (9:31 AM, after the box 18A change): Accrued changed after the last import, 3 fields.
  c: {
    ...BASE,
    state: "out_of_sync",
    allowed_actions: ["tax_return.read", "engine_import.create"],
    blockers: [{ kind: "final_approval_required", ref_id: null }],
    history: [
      event("changed-18a", "changed_after_import", "2026-09-14T09:31:00-05:00", {
        field_keys: ["f1040.l2a", "it201.l20", "it201.l33"],
      }),
      IMPORTED_V3,
      IMPORTED_V2,
    ],
  },
  // d (11:43 AM): exported; the engine's diagnostics came back, 0 errors · 2 informational.
  d: {
    ...BASE,
    state: "synced",
    synced_at: "2026-09-16T11:44:00-05:00",
    history: [
      event("diagnostics-v3", "diagnostics", "2026-09-16T11:45:00-05:00", {
        engine_version: V3,
        errors: 0,
        informational: 2,
      }),
      EXPORTED,
      IMPORTED_V3,
      IMPORTED_V2,
    ],
    diagnostics: [...INFORMATIONAL],
  },
  // d2 (11:20 AM): the error variant; an Identity Protection PIN is required.
  d2: {
    ...BASE,
    state: "failed",
    history: [
      event("diagnostics-failed", "diagnostics", "2026-09-16T11:21:00-05:00", {
        engine_version: V3,
        errors: 1,
        informational: 0,
      }),
      IMPORTED_V3,
      IMPORTED_V2,
    ],
    diagnostics: [
      {
        code: "EFILE_IP_PIN_REQUIRED",
        severity: "error",
        field_key: "f1040.ip_pin.primary",
        message_text:
          "Federal e-file — Identity Protection PIN required for the primary taxpayer (Jonah Feld)",
        issue_id: stableId("issue:feld-ip-pin"),
      },
    ],
  },
  // e (Thu Sep 10, 9:30 AM, In review · Manager): the V3 import waits for approval.
  e: {
    ...BASE,
    state: "import_pending_approval",
    allowed_actions: ["tax_return.read", "engine_import.approve"],
    blockers: [{ kind: "final_approval_required", ref_id: null }],
    history: [
      event("upload-v3", "import_uploaded", "2026-09-10T09:28:00-05:00", { engine_version: V3 }),
      IMPORTED_V2,
    ],
  },
  // Non-artboard: before any export, and after one generated but not yet marked exported.
  not_yet_exported: { ...BASE, state: "not_yet_exported", history: [IMPORTED_V3] },
};

export const FELD_IMPORT_ID = stableId("engine-import:feld-v3");

/** One decimal place, by integer arithmetic (46.0 for 141,634 of 307,900). */
const pct = (amount: number): string => {
  const tenths = Math.round((amount * 1000) / FELD_STATE_TOTAL);
  return `${String(Math.floor(tenths / 10))}.${String(tenths % 10)}`;
};
const fmt = (n: number): string => count(String(n));
const [IL, CO] = FELD_STATE_INCOME;

/** TAX-09 e: the five fields CCH Axcess holds that Accrued does not, none against a workpaper. */
export const FELD_IMPORT: EngineImportOut = {
  id: FELD_IMPORT_ID,
  return_id: FELD_RETURN_ID,
  kind: "values",
  status: "pending_approval",
  uploaded_at: "2026-09-10T09:28:00-05:00",
  allowed_actions: ["engine_import.approve"],
  rows: [
    {
      field_key: "f1040es.2026.vouchers",
      accrued: null,
      engine: String(FELD_ESTIMATE.quarterly),
      cause_code: "entered_in_engine",
      engine_display: `${String(FELD_ESTIMATE.quarters)} × ${fmt(FELD_ESTIMATE.quarterly)}`,
      cause_facts: {
        by: "Samuel Ito",
        pct: String(FELD_ESTIMATE.safeHarbourPct),
        tax: fmt(FELD_ESTIMATE.tax2025),
        safe_harbour: fmt(
          Math.round((FELD_ESTIMATE.tax2025 * FELD_ESTIMATE.safeHarbourPct) / 100),
        ),
        withholding: fmt(FELD_ESTIMATE.withholding),
        balance: fmt(FELD_ESTIMATE.quarterly * FELD_ESTIMATE.quarters),
        quarters: String(FELD_ESTIMATE.quarters),
      },
    },
    {
      field_key: "refund.direct_deposit",
      accrued: null,
      engine: null,
      cause_code: "direct_deposit_authorization",
      engine_display: "Claire Feld · checking ••6620",
      cause_facts: { on: "Aug 28" },
    },
    {
      field_key: "f8879.signature_method",
      accrued: null,
      engine: null,
      cause_code: "firm_default",
      engine_display: "Practitioner PIN",
      cause_facts: {},
    },
    {
      field_key: "il1040.schnr.il_income",
      accrued: null,
      engine: String(IL.amount),
      cause_code: "engine_state_allocation",
      engine_display: null,
      cause_facts: { pct: pct(IL.amount), total: fmt(FELD_STATE_TOTAL) },
    },
    {
      field_key: "co0104pn.co_income",
      accrued: null,
      engine: String(CO.amount),
      cause_code: "engine_state_allocation",
      engine_display: null,
      cause_facts: { pct: pct(CO.amount), total: fmt(FELD_STATE_TOTAL) },
    },
  ],
};
