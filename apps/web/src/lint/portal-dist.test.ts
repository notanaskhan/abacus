// P-08-T07 acceptance: "vite build --mode portal emits dist/portal with no firm chunk, no Accrued
// string and no fixture string". scripts/portal-dist-check.mjs runs after `build:portal`; this
// holds its rules on synthetic builds.
import { beforeAll, describe, expect, it } from "vitest";

interface Check {
  portalProblems: (
    manifest: Record<string, { file: string; src?: string }>,
    files: Record<string, string>,
  ) => string[];
}

const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
let check: Check;

beforeAll(async () => {
  check = (await import(/* @vite-ignore */ `${cwd}/scripts/portal-dist-check.mjs`)) as Check;
});

const CLEAN = {
  "portal.html": { file: "assets/portal.js", src: "portal.html" },
  "src/screens/POR-01/index.tsx": {
    file: "assets/POR-01.js",
    src: "src/screens/POR-01/index.tsx",
  },
  "src/portal/PortalShell.tsx": {
    file: "assets/PortalShell.js",
    src: "src/portal/PortalShell.tsx",
  },
};

describe("the portal dist check", () => {
  it("passes a portal of portal chunks and the footer's sanctioned label", () => {
    expect(
      check.portalProblems(CLEAN, {
        "assets/portal.js": "function w({size:e=20,label:t=`Accrued`}){}",
        "index.html": "<title>Client portal</title>",
      }),
    ).toEqual([]);
  });

  it("fails a firm chunk: the shell, a firm screen, a legacy screen or the gallery", () => {
    for (const src of [
      "src/shell/firm/ToolbarData.tsx",
      "src/screens/CLI-01/index.tsx",
      "src/legacy/ClientHome.tsx",
      "src/gallery/pages.tsx",
      "src/routes/firm/clients.tsx",
    ]) {
      const problems = check.portalProblems({ ...CLEAN, [src]: { file: "assets/x.js", src } }, {});
      expect(problems, src).toHaveLength(1);
    }
  });

  it("fails the product's name anywhere else, in any case", () => {
    for (const text of [
      "<title>Accrued</title>",
      "Secured by ACCRUED",
      "label:t=`Accrued`;x=`accrued`",
    ]) {
      expect(check.portalProblems(CLEAN, { "assets/portal.js": text }), text).not.toEqual([]);
    }
  });

  it("fails a fixture string: Brightwater, Northwind or scenario", () => {
    for (const text of ["Brightwater Hale", "Northwind Robotics", "scenario"]) {
      expect(check.portalProblems(CLEAN, { "assets/POR-01.js": text }), text).toHaveLength(1);
    }
  });
});
