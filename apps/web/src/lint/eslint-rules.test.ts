// The architecture rules in apps/web/eslint.config.js, exercised through ESLint's Node API
// (ADR-011: only the generated client calls the backend; ADR-065: model text only via AgentText).
// Type-aware linting is switched off for these snippets: the rules under test are syntactic.
import { ESLint } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({
  overrideConfig: [tseslint.configs.disableTypeChecked],
});

async function violations(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  const fatal = result?.messages.filter((m) => m.fatal === true) ?? [];
  expect(fatal.map((m) => m.message)).toEqual([]);
  return (result?.messages ?? [])
    .filter(
      (m) =>
        m.ruleId === "no-restricted-syntax" || m.ruleId?.startsWith("no-restricted-") === true,
    )
    .map((m) => `${m.ruleId ?? ""}: ${m.message}`);
}

describe("ac18 ESLint architecture rules", () => {
  it("bans dangerouslySetInnerHTML", async () => {
    const found = await violations(
      "export const A = ({ h }: { h: string }) => <div dangerouslySetInnerHTML={{ __html: h }} />;",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.includes("Never render HTML"))).toBe(true);
  });

  it("bans dangerouslySetInnerHTML on any element", async () => {
    const found = await violations(
      "export const A = () => <p dangerouslySetInnerHTML={{ __html: 'x' }} />;",
      "src/components/Another.tsx",
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it("bans fetch outside src/auth/session.ts", async () => {
    const found = await violations(
      "export const load = () => fetch('/v1/me');",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.startsWith("no-restricted-globals"))).toBe(true);
  });

  it("bans XMLHttpRequest outside src/auth/session.ts", async () => {
    const found = await violations(
      "export const x = new XMLHttpRequest();",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.startsWith("no-restricted-globals"))).toBe(true);
  });

  it("allows fetch in src/auth/session.ts only", async () => {
    const code = "export const token = () => fetch('http://idp/token');";
    expect(await violations(code, "src/auth/session.ts")).toEqual([]);
    expect((await violations(code, "src/auth/other.ts")).length).toBeGreaterThan(0);
  });

  it("bans importing axios", async () => {
    const found = await violations(
      "import axios from 'axios';\nexport const x = axios;",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.startsWith("no-restricted-imports"))).toBe(true);
  });

  it("bans .rationale rendered outside AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string } }) => <p>{r.rationale}</p>;",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.includes("AgentText"))).toBe(true);
  });

  it("bans .quote rendered outside AgentText", async () => {
    const found = await violations(
      "export const A = ({ c }: { c: { quote: string } }) => <q>{c.quote}</q>;",
      "src/screens/Example.tsx",
    );
    expect(found.some((m) => m.includes("AgentText"))).toBe(true);
  });

  it("bans model text behind && and ?: inside JSX", async () => {
    const and = await violations(
      "export const A = ({ c }: { c: { quote: string | null } }) => <p>{c.quote && c.quote}</p>;",
      "src/screens/Example.tsx",
    );
    const cond = await violations(
      "export const A = ({ c }: { c: { rationale: string } }) => <p>{c.rationale ? c.rationale : null}</p>;",
      "src/screens/Example.tsx",
    );
    expect(and.length).toBeGreaterThan(0);
    expect(cond.length).toBeGreaterThan(0);
  });

  it("bans model text passed to an element other than AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string } }) => <p title={r.rationale}>x</p>;",
      "src/screens/Example.tsx",
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it("allows model text as the text of AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string; quote: string } }) => (\n" +
        "  <div><AgentText text={r.rationale} /><AgentText inline text={r.quote} /></div>\n" +
        ");",
      "src/screens/Example.tsx",
    );
    expect(found).toEqual([]);
  });

  it("does not object to ordinary JSX and fields with other names", async () => {
    const found = await violations(
      "export const A = ({ e }: { e: { name: string } }) => <p>{e.name}</p>;",
      "src/screens/Example.tsx",
    );
    expect(found).toEqual([]);
  });
});
