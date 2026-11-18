// INV-4 (DEC-01): the portal build drops the firm-only status codes whose key names the product;
// nothing else in the generated registry changes (vite.config.ts `portalStatuses`).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { dropProductKeyedCodes } from "../../vite.config";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const SOURCE = readFileSync(
  join(process.cwd(), "..", "..", "packages", "ui", "src", "status.gen.ts"),
  "utf8",
);

describe("portal status registry", () => {
  it("drops exactly the product-keyed codes", () => {
    const keyed = [...SOURCE.matchAll(/^ {4}"([a-z0-9_]*accrued[a-z0-9_]*)": \{$/gm)].map(
      (m) => m[1],
    );
    expect(keyed.sort()).toEqual(["accrued_tie_out_shadow", "sent_to_accrued"]);
    const dropped = dropProductKeyedCodes(SOURCE);
    expect(/accrued/i.test(dropped.replace(/\$\{PRODUCT\}/g, ""))).toBe(false);
    const codes = (text: string): number => (text.match(/^ {4}"[a-z0-9_]+": \{$/gm) ?? []).length;
    expect(codes(SOURCE) - codes(dropped)).toBe(keyed.length);
  });
});
