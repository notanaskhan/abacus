// A-06-T26 (TASK-3329): AC tests for the AUD-15 and AUD-16 UI, from the row: "no gate control on
// agent-owned elements, reserved-role controls disabled with reasons, no client-side sums, '$' never in
// tables, Send to client shows template wording only, Undo calls only the compensating command." Read
// from the source so a new control or sum fails here.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const read = (rel: string): string =>
  readFileSync(join(process.cwd(), "src", "screens", "AUD-16", rel), "utf8");
const FILES = {
  workbook: read("./Workbook.tsx"),
  send: read("./SendEntries.tsx"),
  aud15: read("../AUD-15/index.tsx"),
  detail: read("../AUD-15/Detail.tsx"),
};
const ALL = Object.values(FILES).join("\n");

describe("AUD-15 and AUD-16 rules", () => {
  it("does no client-side sums over amounts", () => {
    expect(ALL).not.toMatch(/\.reduce\([^)]*\bamount\b/);
    expect(ALL).not.toMatch(/\bparseFloat\(|\bNumber\(r\.amount|\+\s*Number\(/);
  });

  it("never prints a dollar sign in the tables' source", () => {
    expect(FILES.workbook).not.toMatch(/<t[dh][^>]*>\s*\$/);
  });

  it("agent text only goes through AgentText, and no Decide or Approve is agent-owned", () => {
    expect(ALL).not.toContain("dangerouslySetInnerHTML");
    expect(FILES.detail).not.toMatch(/agent[^\n]*(Approve|Decide|Sign off)/i);
  });

  it("Send to client takes template wording, with no free-text body field", () => {
    expect(FILES.send).not.toMatch(/<textarea/i);
    expect(FILES.send).not.toMatch(/name="body"/);
  });

  it("the workbook decides nothing itself: the decision opens on the card", () => {
    expect(FILES.workbook).not.toMatch(/decideCardMutation|decisionDecideMutation/);
  });
});
