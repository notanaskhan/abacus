// ac-test-author: ayushkbhatia
// F-04-T36 (ADR-078) for F-04-T17's ESLint half: a new direct read of the wall clock (`Date.now()`
// or a bare `new Date()`) fails lint anywhere outside the clock file, in screens, features, the
// portal and plain modules alike, while the clock file itself and dated constructors stay legal.
// Expectations from the F-04-T17 row ("both rules fail on a new direct now() outside
// kernel/clock.py or lib/clock.tsx while main stays green"); the Python half is
// backend/tests/unit/quality/test_f04t36_independent.py.
import { ESLint } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ overrideConfig: [tseslint.configs.disableTypeChecked] });

async function restricted(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  const fatal = result?.messages.filter((m) => m.fatal === true) ?? [];
  expect(fatal.map((m) => m.message)).toEqual([]);
  return (result?.messages ?? [])
    .filter((m) => m.ruleId?.startsWith("no-restricted-") === true)
    .map((m) => `${m.ruleId ?? ""}: ${m.message}`);
}

const NEW_CODE = [
  "src/legacy/Example.tsx",
  "src/features/engagements/Example.tsx",
  "src/portal/routes/Example.tsx",
  "src/app-core/Example.ts",
];

describe("F-04-T17 the wall clock is read only through the clock file", () => {
  it.each(NEW_CODE)("fails on Date.now() in %s", async (file) => {
    expect((await restricted("export const t = () => Date.now();", file)).length).toBeGreaterThan(
      0,
    );
  });

  it.each(NEW_CODE)("fails on a bare new Date() in %s", async (file) => {
    expect((await restricted("export const t = () => new Date();", file)).length).toBeGreaterThan(
      0,
    );
  });

  it("allows both in the clock file", async () => {
    const code = "export const now = () => Date.now();\nexport const at = () => new Date();";
    expect(await restricted(code, "src/app-core/clock.tsx")).toEqual([]);
  });

  it("allows a dated constructor, which reads no clock", async () => {
    const code = "export const at = (iso: string) => new Date(iso);";
    expect(await restricted(code, "src/features/engagements/Example.tsx")).toEqual([]);
  });
});
