// F-04-T10 (SPEC-307 AC-1; F-04.21): the interim TS seed and the Python Brightwater Hale scenario
// produce the same 184 clients, row for row. The golden file is shared; the backend checks the
// Python side (tests/unit/scenarios/test_brightwater_hale.py), this test checks the TS side.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { buildClients } from "./seed/clients";

const GOLDEN = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../backend/tests/golden/scenario/brightwater_hale/clients.json",
);

describe("the TS seed and the Python scenario", () => {
  it("agree on every client, in order", () => {
    const golden = JSON.parse(readFileSync(GOLDEN, "utf8")) as { clients: unknown[] };
    expect(JSON.parse(JSON.stringify(buildClients()))).toEqual(golden.clients);
  });
});
