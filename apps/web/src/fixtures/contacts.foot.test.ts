// CLI-04's figures on the seed (P-07-T33; docs/screens/CLI-04.md, Figures): Northwind's header
// 3 + 1 + 2 = 6, the footer 10 + 9 + 2 + 2 + 1 = 24 with 11 received, Copperleaf's two, and
// every body the handler serves checked against the OpenAPI document.
import type { ContactDetailOut, ContactsPage } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../app-core/fixture-mode";
import { contactHandlers } from "./handlers/contacts";
import { validateSchema } from "./schema-check";
import { getSeed } from "./seed";
import { COPPERLEAF, NORTHWIND, clientIdOf } from "./seed/client-records";

const seed = getSeed();

function request(path: string, params: Record<string, string>): FixtureRequest {
  return {
    method: "GET",
    path,
    params,
    query: new URLSearchParams(),
    body: null,
    persona: "grace-holloway",
  };
}

async function page(clientName: string): Promise<ContactsPage> {
  const handler = contactHandlers(seed)["GET /v1/clients/{client_id}/contacts"];
  if (handler === undefined) throw new Error("no handler");
  const answer = await handler(
    request("/v1/clients/x/contacts", { client_id: clientIdOf(clientName) }),
  );
  return (await answer.json()) as ContactsPage;
}

describe("CLI-04 footing on the seed", () => {
  it("a: 3 active · 1 invited · 2 not invited; 10 + 9 + 2 + 2 + 1 = 24, received 11 of 24", async () => {
    const a = await page(NORTHWIND);
    expect(validateSchema("ContactsPage", a)).toEqual([]);
    expect(a.items).toHaveLength(6);
    expect(a.summary).toEqual({ active: 3, invited: 1, not_invited: 2, locked: 0 });
    expect(a.delegated).toEqual({ parts: [10, 9, 2, 2, 1], total: 24, received: 11 });
    // Every one of Northwind's 24 PBC requests is delegated once.
    const handlers = contactHandlers(seed);
    const ids: string[] = [];
    for (const row of a.items) {
      const detail = handlers["GET /v1/contacts/{contact_id}"];
      if (detail === undefined) throw new Error("no detail");
      const body = (await (
        await detail(request(`/v1/contacts/${row.id}`, { contact_id: row.id }))
      ).json()) as ContactDetailOut;
      expect(validateSchema("ContactDetailOut", body)).toEqual([]);
      ids.push(...(body.delegated_request_ids ?? []));
    }
    expect(new Set(ids).size).toBe(24);
  });

  it("g: Copperleaf's owner and controller, both active, nothing delegated", async () => {
    const g = await page(COPPERLEAF);
    expect(g.items.map((r) => r.name)).toEqual(["Tess Moreno", "Ben Ashby"]);
    expect(g.summary).toEqual({ active: 2, invited: 0, not_invited: 0, locked: 0 });
    expect(g.delegated).toEqual({ parts: [], total: 0, received: 0 });
  });
});
