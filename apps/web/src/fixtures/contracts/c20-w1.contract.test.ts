// C-02-T08 (DEC-5507): C20 v2.1 W1 consumer fixtures for CLS-11 and POR-16
// (docs/contracts/c20-integrations.md v2.1; SPEC-700 AC-3, AC-24). Typed with the generated
// client and checked against the OpenAPI document. Copperleaf's console at 9:24 AM, Sep 14, 2026.
// The pytest half is backend/tests/contracts/c20_integrations/test_c02t08_w1_consumer.py.
import type { LedgerConsoleOut, PostingLogRowOut, WriteGrantIn } from "@abacus/api-client";
import { STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";

const CONSOLE = "/v1/client-entities/{client_entity_id}/ledger-console";
const BATCH = "/v1/posting-batches/{batch_id}";
type Entry = { label: string; clientLabel?: string };
const GRANT = STATUS_REGISTRY.ledger_write_grant as Record<string, Entry>;

const cls11a: LedgerConsoleOut = {
  client_entity_id: "00000000-0000-4000-8000-0000000000c1",
  client_entity_name: "Copperleaf Coffee Roasters, Inc.",
  ledger_label: "QuickBooks Online",
  tiles: {
    posted: 7,
    proposed: 1,
    failed_post: 0,
    resolved_failures: 1,
    closing_date: "2026-07-31",
  },
  connection: {
    connection_id: "00000000-0000-4000-8000-0000000000d1",
    health: "connected",
    authorized_by: "Tess Moreno (client portal)",
    write_granted: true,
    last_sync_at: "2026-09-14T14:02:00Z",
    last_sync_transactions: 1214,
    last_sync_errors: 0,
    next_sync_at: "2026-09-14T15:02:00Z",
    closing_date: "2026-07-31",
    closing_date_set_by: "Raj Malhotra",
    dependents: [],
  },
};

describe("C20 v2.1 fixtures for CLS-11 and POR-16", () => {
  it("a: the console's tiles and pane match the OpenAPI document", () => {
    expect(validateResponse("GET", CONSOLE, cls11a)).toEqual([]);
    expect(cls11a.tiles).toMatchObject({ posted: 7, proposed: 1, closing_date: "2026-07-31" });
  });

  it("b: the July batch reads its resolved failure", () => {
    const row: PostingLogRowOut = {
      batch_id: "00000000-0000-4000-8000-0000000007a0",
      batch_code: "2026-07-A",
      period: "2026-07",
      status: "posted",
      entry_count: 6,
      approved_count: 6,
      first_external_ref: "47602",
      last_external_ref: "47607",
      resolved_failures: 1,
    };
    expect(validateResponse("GET", BATCH, row)).toEqual([]);
  });

  it("POR-16: the grant names consent copy v2 and the registry's words", () => {
    const grant: WriteGrantIn = {
      capability_id: "ledger_post_journal_entries",
      consent_copy_version: "por16.qbo.post_entries.v2",
    };
    expect(grant.consent_copy_version).toBe("por16.qbo.post_entries.v2");
    expect(GRANT.revoked?.label).toBe("Posting paused");
  });
});
