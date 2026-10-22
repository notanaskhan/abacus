// F-05-T39 acceptance (INV-4; DEC-59, ADR-163; plan 04 lint L7): "portal entries cannot import firm
// shell or firm screens", and portal code never carries the product's name. Exercised through
// ESLint's Node API on both configs (apps/web and packages/ui); type-aware linting is off because
// the rules under test are syntactic.
import { ESLint } from "eslint";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const UI = join(WEB, "..", "..", "packages", "ui");

const web = new ESLint({ cwd: WEB, overrideConfig: [tseslint.configs.disableTypeChecked] });
const ui = new ESLint({ cwd: UI, overrideConfig: [tseslint.configs.disableTypeChecked] });

async function found(eslint: ESLint, code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  const fatal = result?.messages.filter((m) => m.fatal === true) ?? [];
  expect(fatal.map((m) => m.message)).toEqual([]);
  return (result?.messages ?? [])
    .filter((m) => m.ruleId?.startsWith("no-restricted-") === true)
    .map((m) => `${m.ruleId ?? ""}: ${m.message}`);
}

const imports = (source: string): string =>
  `import { x } from "${source}";\nexport const y = x;\n`;
const inv4 = (messages: string[]): boolean =>
  messages.some((m) => m.startsWith("no-restricted-imports") && m.includes("INV-4"));

describe("INV-4: portal entries cannot import the firm shell or firm screens", () => {
  const CASES: readonly (readonly [file: string, source: string])[] = [
    ["src/entries/portal.tsx", "../shell/firm/toolbar"],
    ["src/entries/portal.tsx", "../shell/nav"],
    ["src/entries/portal.tsx", "../routes/firm"],
    ["src/entries/portal.tsx", "../routes/root"],
    ["src/entries/portal.tsx", "../screens/SHL-01"],
    ["src/entries/portal.tsx", "../legacy/Layout"],
    ["src/entries/portal.tsx", "../gallery/pages"],
    ["src/entries/portal.tsx", "@abacus/ui/specimens"],
    ["src/portal/home.tsx", "../shell/Palette"],
    ["src/routes/portal/public.tsx", "../firm/home"],
    ["src/routes/portal/public.tsx", "../../shell/firm/toolbar"],
    ["src/screens/POR-03/index.tsx", "../../shell/firm/toolbar"],
    ["src/screens/POR-03/index.tsx", "../SHL-01/index"],
    ["src/screens/POR-03/index.tsx", "../AUD-02"],
  ];

  for (const [file, source] of CASES) {
    it(`${file} may not import ${source}`, async () => {
      expect(inv4(await found(web, imports(source), file))).toBe(true);
    });
  }

  it("the portal imports what it may: the design system, app-core, its own screens", async () => {
    const ok: readonly (readonly [string, string])[] = [
      ["src/entries/portal.tsx", "@abacus/ui"],
      ["src/entries/portal.tsx", "../app-core/session"],
      ["src/entries/portal.tsx", "../screens/POR-01"],
      ["src/screens/POR-03/index.tsx", "../POR-04/index"],
      ["src/screens/POR-03/index.tsx", "../../app-core/clock"],
    ];
    for (const [file, source] of ok) {
      expect(await found(web, imports(source), file), `${file} ← ${source}`).toEqual([]);
    }
  });

  it("the firm's own code keeps its shell", async () => {
    expect(
      inv4(await found(web, imports("../../shell/firm/toolbar"), "src/screens/SHL-01/x.tsx")),
    ).toBe(false);
  });
});

describe("L7: portal code never renders the product's name", () => {
  const SNIPPETS = [
    'export const title = "Accrued client portal";',
    "export const t = `Secured by accrued`;",
    "export const A = () => <span>Powered by ACCRUED</span>;",
  ];

  for (const file of ["src/entries/portal.tsx", "src/screens/POR-02/index.tsx"]) {
    it(`fails in ${file}`, async () => {
      for (const code of SNIPPETS) {
        const messages = await found(web, code, file);
        expect(
          messages.some((m) => m.includes("product's name")),
          `${file}: ${code}`,
        ).toBe(true);
      }
    });
  }

  it("fails in packages/ui's portal surfaces and their specimens", async () => {
    for (const file of [
      "src/templates/portal-layout.tsx",
      "src/templates/auth-card.tsx",
      "src/requests/parts.tsx",
      "src/layout/mobile-tab-bar.tsx",
      "src/specimens/requests.tsx",
    ]) {
      const messages = await found(ui, SNIPPETS[0] ?? "", file);
      expect(
        messages.some((m) => m.includes("product's name")),
        file,
      ).toBe(true);
    }
  });

  it("leaves the firm app and the firm's name alone", async () => {
    expect(
      (await found(web, SNIPPETS[0] ?? "", "src/screens/SHL-01/x.tsx")).filter((m) =>
        m.includes("product's name"),
      ),
    ).toEqual([]);
    expect(
      await found(web, 'export const firm = "Brightwater Hale";', "src/entries/portal.tsx"),
    ).toEqual([]);
  });
});
