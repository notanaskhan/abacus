// A-02-T08 (TASK-1263): C20 v1 consumer fixtures for POR-16 (docs/contracts/c20-integrations.md;
// SPEC-333 AC-35, AC-36, AC-38). Typed with the generated client, so a breaking change fails
// `tsc`, and checked against the OpenAPI document at run time. Copperleaf's cards at E0 from the
// POR-16 handoff, with DF-19's mask (no posting copy). The pytest half is
// backend/tests/contracts/c20_integrations/.
import type { IntegrationStatus, PortalConnectionsOut } from "@abacus/api-client";
import { type EnumCovered, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { connectionsHandlers } from "../handlers/connections";
import { validateResponse } from "../schema-check";
import { scenarios } from "../scenarios/POR-16";
import {
  COPPERLEAF_ENTITY_ID,
  IDS,
  POR16_CLOCKS,
  type Por16State,
  copperleafConnections,
} from "../seed/connections";

const STATES: readonly Por16State[] = ["a", "b", "c", "d", "e", "f", "g"];
const LIST = "/v1/portal/entities/{entity_id}/connections";
type Entry = { label: string; clientLabel?: string };
const INTEGRATION = STATUS_REGISTRY.integration as Record<string, Entry>;

// The generated enum is exactly the registry's object (C2).
const covered: EnumCovered<"integration", IntegrationStatus> = true;

function request(path: string, params: Record<string, string>, body?: unknown): FixtureRequest {
  return { method: "POST", path, params, query: new URLSearchParams(), body, persona: undefined };
}

/** The words POR-16 a shows on each card: the registry's, the client's where they differ. */
function words(page: PortalConnectionsOut): Record<string, string | undefined> {
  return Object.fromEntries(
    page.items.map((c) => {
      const entry = INTEGRATION[c.status];
      return [c.name, entry?.clientLabel ?? entry?.label];
    }),
  );
}

describe("C20 v1 fixtures for POR-16", () => {
  it("covers the registry's integration codes and reads Not connected on the portal", () => {
    expect(covered).toBe(true);
    expect(words(copperleafConnections("a"))).toEqual({
      "QuickBooks Online": "Connected",
      "Front Range Bank": "Connected",
      "American Express": "Needs reauth",
      Square: "Connected",
      Shopify: "Not connected",
      "Payroll provider": "Not connected",
    });
  });

  it("serves a to g as typed scenarios that match the OpenAPI document", () => {
    expect(Object.keys(scenarios)).toEqual(STATES);
    for (const state of STATES) {
      expect(validateResponse("GET", LIST, copperleafConnections(state))).toEqual([]);
      expect(scenarios[state].persona).toBe("tess-moreno");
    }
    expect(scenarios.e.clock).toBe(POR16_CLOCKS.e);
  });

  it("reads Tess's QuickBooks connection, the masked labels and the reconnect", () => {
    const [quickbooks, bank, amex] = copperleafConnections("a").items;
    expect(quickbooks?.connected_by?.display_name).toBe("Tess Moreno");
    expect(quickbooks?.connected_by?.kind).toBe("client");
    expect(quickbooks?.connected_at?.slice(0, 10)).toBe("2026-03-04");
    expect(bank?.display_label).toBe("Front Range Bank ••4410");
    expect(amex?.display_label).toBe("American Express ••1009");
    expect(amex?.status_reason).toBe("token_expired");
    expect(copperleafConnections("c").items[2]?.status).toBe("connecting");
    const reconnected = copperleafConnections("d").items[2];
    expect([reconnected?.status, reconnected?.reconnected]).toEqual(["connected", true]);
    expect(copperleafConnections("g").items[3]?.status).toBe("needs_attention");
  });

  it("offers no write anywhere and Export instead on every ledger card (DF-19, ADR-108)", () => {
    for (const state of STATES) {
      const page = copperleafConnections(state);
      const text = JSON.stringify(page).toLowerCase();
      expect(text).not.toMatch(/post entries|posts only|post approved|accept entries/);
      for (const card of page.items) {
        expect(card.scopes?.every((s) => s.code.endsWith(".read"))).toBe(true);
        if (card.category === "ledger") {
          expect(card.export_instead).not.toBeNull();
          expect(card.allowed_actions).toContain("export_instead");
        }
      }
    }
  });

  it("never names Accrued on the portal (white label)", () => {
    for (const state of STATES) {
      expect(JSON.stringify(copperleafConnections(state))).not.toMatch(/accrued/i);
    }
  });

  it("refuses a start without the authorization, and an old consent copy", async () => {
    const handlers = connectionsHandlers("b", { clock: POR16_CLOCKS.a });
    const start = handlers[`POST ${LIST}/{catalog_key}/start`];
    const params = { entity_id: COPPERLEAF_ENTITY_ID, catalog_key: "american_express" };
    const path = `/v1/portal/entities/${COPPERLEAF_ENTITY_ID}/connections/american_express/start`;
    const refused = await start?.(
      request(path, params, { consent_version: 1, authorized: false }),
    );
    expect(refused?.status).toBe(422);
    expect(await refused?.json()).toEqual({ detail: "authorization_required" });
    const stale = await start?.(request(path, params, { consent_version: 9, authorized: true }));
    expect(stale?.status).toBe(409);
    const ok = await start?.(request(path, params, { consent_version: 1, authorized: true }));
    expect(ok?.status).toBe(201);
  });

  it("answers 404 for another entity and returns the same run on a second Try again", async () => {
    const handlers = connectionsHandlers("g", { clock: POR16_CLOCKS.a });
    const other = await handlers[`GET ${LIST}`]?.({
      ...request("/", { entity_id: "00000000-0000-0000-0000-000000000000" }),
      method: "GET",
    });
    expect(other?.status).toBe(404);
    const retry = handlers["POST /v1/portal/connections/{connection_id}/retry"];
    const params = { connection_id: IDS.square };
    const first: unknown = await (await retry?.(request("/", params)))?.json();
    const second: unknown = await (await retry?.(request("/", params)))?.json();
    expect(second).toEqual(first);
  });
});
