// F-07-T20 (TASK-7921; F-07 §I3; INV-4, DEC-78, DEC-88): "Tests fail on … a portal import of a
// firm-only kit." The portal entry, tree, routes and POR screens may not import agent/chat, graph
// or forms-gov; the firm's own screens still may.
import { ESLint } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ overrideConfig: [tseslint.configs.disableTypeChecked] });

async function restricted(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? [])
    .filter((m) => m.ruleId === "no-restricted-imports")
    .map((m) => m.message);
}

const KITS = [
  'import { GraphCanvas } from "@abacus/ui";',
  'import { GraphCanvasLayout } from "@abacus/ui";',
  'import { FormRendererLayout } from "@abacus/ui";',
  'import { ChatThread, SessionList } from "@abacus/ui";',
  'import { WorkbenchLayout } from "@abacus/ui";',
];

describe("F-07-T20 portal boundary: firm-only kits", () => {
  for (const code of KITS) {
    for (const file of [
      "src/entries/portal.tsx",
      "src/portal/home.tsx",
      "src/screens/POR-04/index.tsx",
    ]) {
      it(`refuses ${code} in ${file}`, async () => {
        const found = await restricted(`${code}\nexport const x = 1;`, file);
        expect(found.some((m) => m.includes("firm-only"))).toBe(true);
      });
    }
  }

  it("refuses a deep import of a firm-only kit's folder", async () => {
    const found = await restricted(
      'import { x } from "../../../packages/ui/src/graph/canvas";\nexport const y = x;',
      "src/portal/home.tsx",
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it("a portal file may still import shared kits", async () => {
    const found = await restricted(
      'import { Button } from "@abacus/ui";\nexport const B = Button;',
      "src/portal/home.tsx",
    );
    expect(found).toEqual([]);
  });

  it("a firm screen may import the graph", async () => {
    const found = await restricted(
      'import { GraphCanvas } from "@abacus/ui";\nexport const G = GraphCanvas;',
      "src/screens/CLI-02/index.tsx",
    );
    expect(found.some((m) => m.includes("firm-only"))).toBe(false);
  });
});
