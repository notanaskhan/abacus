// P-02-T02 (TASK-7506): C15 v1 consumer assertions for SHL-02 (docs/contracts/c15-search.md).
// Typed with the generated client, so a breaking change fails `tsc`, and checked against the
// OpenAPI document at run time. The pytest half is backend/tests/contracts/c15_search/.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type {
  SearchQueryIn,
  SearchRecentRecordedOut,
  SearchRecentsOut,
  SearchResultsOut,
} from "@abacus/api-client";
import { validateResponse, validateSchema } from "../schema-check";

const here = dirname(fileURLToPath(import.meta.url));
const SPEC_TEXT = readFileSync(
  join(here, "..", "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
  "utf8",
);
const SPEC = JSON.parse(SPEC_TEXT) as {
  paths: Record<string, Record<string, { parameters?: { name: string; in: string }[] }>>;
};

const FELD_RETURN = "6f1d2c3b-4a59-4e6f-8a7b-9c0d1e2f3a4b";
const FELD_CLIENT = "0b1c2d3e-4f50-4617-a8b9-c0d1e2f3a4b5";

// SHL-02a's "Returns" row as the server would send it: identifiers in the target, the C2 code
// and context, never the status words (they come from status.ts).
const RESULTS: SearchResultsOut = {
  groups: [
    {
      group: "returns",
      has_more: false,
      items: [
        {
          object_type: "tax_return",
          object_id: FELD_RETURN,
          title: "2025 Form 1040",
          context: "Jonah & Claire Feld · due Oct 15, 2026",
          status: { code: "in_review", context: "manager" },
          target: { screen_id: "TAX-02", params: { returnId: FELD_RETURN } },
          match_ranges: [],
        },
      ],
    },
  ],
  suggestion: null,
  total_visible: 1,
};

describe("C15 v1 consumer (SHL-02)", () => {
  it("POST /v1/search answers the grouped shape", () => {
    expect(validateResponse("post", "/v1/search", RESULTS)).toEqual([]);
  });

  it("the recents read and write answer identifiers and items only", () => {
    const recents: SearchRecentsOut = { items: RESULTS.groups[0]!.items };
    expect(validateResponse("get", "/v1/search/recents", recents)).toEqual([]);
    const recorded: SearchRecentRecordedOut = { object_type: "client", object_id: FELD_CLIENT };
    expect(validateResponse("post", "/v1/search/recents", recorded)).toEqual([]);
  });

  it("refuses a wall count anywhere in a result", () => {
    const leaked = { ...RESULTS, hidden_by_wall: 2 };
    expect(validateResponse("post", "/v1/search", leaked)).not.toEqual([]);
    expect(SPEC_TEXT).not.toContain("hidden_by_wall");
  });

  it("caps total_visible at 99", () => {
    expect(validateSchema("SearchResultsOut", { ...RESULTS, total_visible: 100 })).not.toEqual(
      [],
    );
  });

  it("sends search text only in the body", () => {
    const query: SearchQueryIn = { q: "feld", limit_per_group: 5 };
    expect(validateSchema("SearchQueryIn", query)).toEqual([]);
    for (const [path, ops] of Object.entries(SPEC.paths)) {
      if (!path.startsWith("/v1/search")) continue;
      for (const op of Object.values(ops)) {
        const names = (op.parameters ?? []).filter((p) => p.in === "query").map((p) => p.name);
        expect(names).not.toContain("q");
      }
    }
  });
});
