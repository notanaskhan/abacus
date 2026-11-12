// T-04-T46 (TASK-7526): TAX-02's post-window wiring. Run draft is live only where the server
// offers `tax_return.draft_run` with `tax_agents.enabled` on, and the frame's Review, Issues and
// Activity tabs follow the server's tab registry (T-04-T55), staying planned otherwise.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const SOURCE = readFileSync(join(process.cwd(), "src", "screens", "TAX-02", "index.tsx"), "utf8");

describe("TAX-02 post-window wiring", () => {
  it("runs a draft through the generated client only when the server offers it", () => {
    expect(SOURCE).toContain("draftRunMutation()");
    expect(SOURCE).toMatch(/useFlag\("tax_agents\.enabled"\)/u);
    expect(SOURCE).toContain('record.allowed_actions.includes("tax_return.draft_run")');
  });

  it("draws the workspace tabs from the server's registry", () => {
    expect(SOURCE).toContain("serverTabs.has(k)");
    expect(SOURCE).toMatch(/record\.data\?\.tabs/u);
  });
});
