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
      "src/legacy/Example.tsx",
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
      "src/legacy/Example.tsx",
    );
    expect(found.some((m) => m.startsWith("no-restricted-globals"))).toBe(true);
  });

  it("bans XMLHttpRequest outside src/auth/session.ts", async () => {
    const found = await violations(
      "export const x = new XMLHttpRequest();",
      "src/legacy/Example.tsx",
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
      "src/legacy/Example.tsx",
    );
    expect(found.some((m) => m.startsWith("no-restricted-imports"))).toBe(true);
  });

  it("bans .rationale rendered outside AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string } }) => <p>{r.rationale}</p>;",
      "src/legacy/Example.tsx",
    );
    expect(found.some((m) => m.includes("AgentText"))).toBe(true);
  });

  it("bans .quote rendered outside AgentText", async () => {
    const found = await violations(
      "export const A = ({ c }: { c: { quote: string } }) => <q>{c.quote}</q>;",
      "src/legacy/Example.tsx",
    );
    expect(found.some((m) => m.includes("AgentText"))).toBe(true);
  });

  it("bans model text behind && and ?: inside JSX", async () => {
    const and = await violations(
      "export const A = ({ c }: { c: { quote: string | null } }) => <p>{c.quote && c.quote}</p>;",
      "src/legacy/Example.tsx",
    );
    const cond = await violations(
      "export const A = ({ c }: { c: { rationale: string } }) => <p>{c.rationale ? c.rationale : null}</p>;",
      "src/legacy/Example.tsx",
    );
    expect(and.length).toBeGreaterThan(0);
    expect(cond.length).toBeGreaterThan(0);
  });

  it("bans model text passed to an element other than AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string } }) => <p title={r.rationale}>x</p>;",
      "src/legacy/Example.tsx",
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it("allows model text as the text of AgentText", async () => {
    const found = await violations(
      "export const A = ({ r }: { r: { rationale: string; quote: string } }) => (\n" +
        "  <div><AgentText text={r.rationale} /><AgentText inline text={r.quote} /></div>\n" +
        ");",
      "src/legacy/Example.tsx",
    );
    expect(found).toEqual([]);
  });

  it("bans writing HTML into the DOM", async () => {
    const snippets = [
      "export const f = (e: HTMLElement, h: string) => { e.innerHTML = h; };",
      "export const f = (e: HTMLElement, h: string) => { e.outerHTML = h; };",
      "export const f = (e: HTMLElement, h: string) => { e.insertAdjacentHTML('beforeend', h); };",
      "export const f = (r: Range, h: string) => r.createContextualFragment(h);",
    ];
    for (const code of snippets) {
      const found = await violations(code, "src/legacy/Example.tsx");
      expect(found.length, code).toBeGreaterThan(0);
    }
  });

  it("bans dangerouslySetInnerHTML passed as an object property", async () => {
    const found = await violations(
      "const props = { dangerouslySetInnerHTML: { __html: 'x' } };\nexport const A = () => <p {...props} />;",
      "src/legacy/Example.tsx",
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it("does not apply the HTML and agent-text rules to test files", async () => {
    const code =
      "export const f = (e: HTMLElement) => { e.innerHTML = '<b>x</b>'; };\n" +
      "export const A = ({ r }: { r: { rationale: string } }) => <p>{r.rationale}</p>;";
    expect(await violations(code, "src/legacy/Example.test.tsx")).toEqual([]);
    expect((await violations(code, "src/legacy/Example.tsx")).length).toBeGreaterThan(0);
  });

  it("still bans fetch and axios in test files", async () => {
    const found = await violations(
      "import axios from 'axios';\nexport const x = [axios, fetch];",
      "src/legacy/Example.test.ts",
    );
    expect(found.some((m) => m.startsWith("no-restricted-imports"))).toBe(true);
    expect(found.some((m) => m.startsWith("no-restricted-globals"))).toBe(true);
  });

  it("does not object to ordinary JSX and fields with other names", async () => {
    const found = await violations(
      "export const A = ({ e }: { e: { name: string } }) => <p>{e.name}</p>;",
      "src/legacy/Example.tsx",
    );
    expect(found).toEqual([]);
  });
});

describe("SPEC-016 design tokens", () => {
  it("ac1 bans Tailwind palette colours in screens", async () => {
    const found = await violations(
      'export const A = () => <p className="bg-neutral-100 text-red-700">x</p>;',
      "src/legacy/Example.tsx",
    );
    expect(found.some((m) => m.includes("design tokens"))).toBe(true);
  });

  it("ac1 bans raw hex colours in screens", async () => {
    const found = await violations('export const c = "#7a4e12";', "src/legacy/Example.tsx");
    expect(found.some((m) => m.includes("raw hex"))).toBe(true);
  });

  it("ac1 allows the tokens", async () => {
    const found = await violations(
      'export const A = () => <p className="bg-surface text-muted border-line">x</p>;',
      "src/legacy/Example.tsx",
    );
    expect(found).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------
// SPEC-048 AC-5 (F-05-T07 rules, F-05-T08 cases). Written first, from the spec, then the rules.
// Each case is one string of the AC. The design rules live in packages/ui/eslint-design-rules.js
// and are shared by apps/web and packages/ui.
// ---------------------------------------------------------------------------------------------

// Vitest stubs CSS imports, so theme.css is read from disk. Node's fs is typed here, not pulled
// into the SPA's build (as tokens.test.ts does).
type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
const webDir = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
const uiDir = webDir.replace(/\/apps\/web$/, "/packages/ui");

interface Rule {
  selector: string;
  message: string;
}
interface DesignRules {
  TYPE_SCALE_BAN_ENABLED: boolean;
  deferredTypeScaleSyntax: Rule[];
}
async function designRules(): Promise<DesignRules> {
  const path = `${uiDir}/eslint-design-rules.js`;
  return (await import(/* @vite-ignore */ path)) as DesignRules;
}
async function tokenNames(): Promise<string[]> {
  const fsModule = "node:fs";
  const fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
  const css = fs.readFileSync(`${uiDir}/src/theme.css`, "utf8");
  return [...css.matchAll(/--color-([a-z0-9-]+):/g)].flatMap((m) =>
    m[1] === undefined ? [] : [m[1]],
  );
}

function restricted(messages: { ruleId: string | null; message: string }[]): string[] {
  return messages
    .filter((m) => m.ruleId?.startsWith("no-restricted-") === true)
    .map((m) => `${m.ruleId ?? ""}: ${m.message}`);
}

const uiEslint = new ESLint({
  cwd: uiDir,
  overrideConfig: [tseslint.configs.disableTypeChecked],
});
async function uiViolations(code: string, filePath: string): Promise<string[]> {
  const [result] = await uiEslint.lintText(code, { filePath: `${uiDir}/${filePath}` });
  expect((result?.messages ?? []).filter((m) => m.fatal === true).map((m) => m.message)).toEqual(
    [],
  );
  return restricted(result?.messages ?? []);
}

const SCREEN = "src/legacy/Example.tsx";
const cls = (value: string): string => `export const A = () => <p className="${value}">x</p>;`;

describe("SPEC-048 ac5 palette: only Accrued token utilities", () => {
  it("rejects bg-neutral-100", async () => {
    expect((await violations(cls("bg-neutral-100"), SCREEN)).length).toBeGreaterThan(0);
  });

  it.each([
    "bg-white",
    "bg-black",
    "text-gray-500",
    "border-slate-200",
    "ring-blue-500",
    "from-zinc-50",
    "to-stone-100",
    "fill-yellow-400",
    "stroke-indigo-600",
    "divide-neutral-200",
    "outline-purple-500",
    "placeholder-pink-300",
    "text-red-700",
    "bg-green-500",
    "border-amber-300",
    "bg-red-50",
    "bg-neutral-100/50",
    "hover:bg-gray-50",
    "dark:text-slate-100",
  ])("rejects the Tailwind palette class %s", async (name) => {
    expect((await violations(cls(name), SCREEN)).length, name).toBeGreaterThan(0);
  });

  it("rejects palette classes in template literals and expressions", async () => {
    const found = await violations(
      "export const f = (on: boolean) => `p-2 ${on ? 'x' : 'y'} bg-neutral-100`;",
      SCREEN,
    );
    expect(found.length).toBeGreaterThan(0);
  });

  // Built from parts: Tailwind scans test files for class names, and these must never compile.
  const arbitrary = (prefix: string, value: string): string => `${prefix}-[${value}]`;
  it.each([
    arbitrary("bg", "#fff"),
    arbitrary("text", "rgb(0,0,0)"),
    arbitrary("border", "hsl(10,10%,10%)"),
    arbitrary("bg", "oklch(0.5_0.1_20)"),
  ])("rejects the arbitrary colour %s", async (name) => {
    expect((await violations(cls(name), SCREEN)).length, name).toBeGreaterThan(0);
  });

  it("accepts bg-green-tint and text-red-ink", async () => {
    expect(await violations(cls("bg-green-tint"), SCREEN)).toEqual([]);
    expect(await violations(cls("text-red-ink"), SCREEN)).toEqual([]);
  });

  it("accepts the bare status tokens green, amber and red", async () => {
    expect(await violations(cls("bg-green text-amber border-red"), SCREEN)).toEqual([]);
  });

  it("accepts every colour token in theme.css under every colour prefix", async () => {
    const names = await tokenNames();
    expect(names.length).toBeGreaterThan(20);
    const classes = names.flatMap((n) => [
      `bg-${n}`,
      `text-${n}`,
      `border-${n}`,
      `ring-${n}`,
      `fill-${n}`,
      `stroke-${n}`,
      `divide-${n}`,
      `bg-${n}/50`,
      `hover:bg-${n}`,
    ]);
    expect(await violations(cls(classes.join(" ")), SCREEN)).toEqual([]);
  });

  it("does not object to utilities that only share a prefix with colours", async () => {
    const ok =
      "text-left text-center border-t border-2 ring-2 ring-offset-2 outline-none fill-current stroke-2 bg-transparent from-10% shadow-e1 shadow-pop";
    expect(await violations(cls(ok), SCREEN)).toEqual([]);
  });

  it("applies in components and in packages/ui, and skips tests", async () => {
    const code = cls("bg-neutral-100");
    expect((await violations(code, "src/components/Example.tsx")).length).toBeGreaterThan(0);
    expect((await uiViolations(code, "src/components/example.tsx")).length).toBeGreaterThan(0);
    expect(await violations(code, "src/legacy/Example.test.tsx")).toEqual([]);
  });
});

describe("SPEC-048 ac5 colour literals", () => {
  it("rejects #7a4e12", async () => {
    expect((await violations('export const c = "#7a4e12";', SCREEN)).length).toBeGreaterThan(0);
  });

  it.each([
    'export const c = "#fff";',
    'export const c = "#7A4E12";',
    'export const c = "#7a4e12cc";',
    "export const c = `border: 1px solid #ccc`;",
    'export const c = "rgba(43, 31, 23, 0.1)";',
    'export const c = "rgb(0 0 0 / 0.5)";',
    'export const c = "hsl(20 10% 10%)";',
    'export const c = "hsla(20, 10%, 10%, .5)";',
    'export const c = "oklch(0.5 0.1 20)";',
    'export const s = { boxShadow: "0 1px 2px rgba(0,0,0,.1)" };',
    'export const A = () => <i style={{ color: "#333" }} />;',
  ])("rejects a colour literal in a screen: %s", async (code) => {
    expect((await violations(code, SCREEN)).length, code).toBeGreaterThan(0);
  });

  it("rejects hex and rgba( in packages/ui outside tokens/ and brand/", async () => {
    const hex = 'export const c = "#7a4e12";';
    const rgba = 'export const c = "rgba(43, 31, 23, 0.1)";';
    for (const file of ["src/components/button.tsx", "src/status.tsx", "src/specimens/a.tsx"]) {
      expect((await uiViolations(hex, file)).length, `${file} hex`).toBeGreaterThan(0);
      expect((await uiViolations(rgba, file)).length, `${file} rgba`).toBeGreaterThan(0);
    }
  });

  it("allows hex and rgba( in packages/ui tokens/ and brand/", async () => {
    const code = 'export const c = ["#7a4e12", "rgba(43, 31, 23, 0.1)"];';
    for (const file of ["src/tokens/colours.ts", "src/brand/mark.tsx"]) {
      expect(await uiViolations(code, file), file).toEqual([]);
    }
  });

  it("does not flag strings that merely contain a # or rgba as a word", async () => {
    const code = 'export const a = ["#channel", "#main-content", "item #12", "rgbalike"];';
    expect(await violations(code, SCREEN)).toEqual([]);
  });
});

describe("SPEC-048 ac5 banned utilities", () => {
  it.each([
    "font-semibold",
    "font-bold",
    "font-extrabold",
    "font-black",
    "font-light",
    "font-thin",
    "md:font-semibold",
    "shadow-lg",
    "shadow-sm",
    "shadow-md",
    "shadow-xl",
    "shadow-2xl",
    "hover:shadow-lg",
  ])("rejects %s", async (name) => {
    expect((await violations(cls(name), SCREEN)).length, name).toBeGreaterThan(0);
  });

  it("accepts font-medium, font-normal, the shadow tokens and the mono family", async () => {
    const ok =
      "font-medium font-normal font-sans font-mono shadow-e1 shadow-e2 shadow-pop shadow-menu shadow-modal shadow-cta inset-shadow-hair";
    expect(await violations(cls(ok), SCREEN)).toEqual([]);
  });

  it("does not match inside longer words", async () => {
    const code = 'export const a = ["semibold text", "shadowless", "bold claim"];';
    expect(await violations(code, SCREEN)).toEqual([]);
  });
});

describe("SPEC-048 ac5 text-lg and the default type scale (deferred until F-05-T06)", () => {
  async function withDeferredSet(): Promise<ESLint> {
    const { deferredTypeScaleSyntax } = await designRules();
    return new ESLint({
      overrideConfig: [
        tseslint.configs.disableTypeChecked,
        {
          files: ["src/**/*.{ts,tsx}"],
          rules: { "no-restricted-syntax": ["error", ...deferredTypeScaleSyntax] },
        },
      ],
    });
  }

  it("matches the flag in the shipped config: flipping TYPE_SCALE_BAN_ENABLED changes it", async () => {
    const { TYPE_SCALE_BAN_ENABLED } = await designRules();
    const found = await violations(cls("text-sm text-lg"), SCREEN);
    expect(found.length > 0).toBe(TYPE_SCALE_BAN_ENABLED);
  });

  it("flags text-xs to text-3xl once the set is enabled", async () => {
    const enabled = await withDeferredSet();
    for (const size of ["xs", "sm", "base", "lg", "xl", "2xl", "3xl"]) {
      const [result] = await enabled.lintText(cls(`text-${size}`), { filePath: SCREEN });
      expect(restricted(result?.messages ?? []).length, `text-${size}`).toBeGreaterThan(0);
    }
    const [responsive] = await enabled.lintText(cls("md:text-lg"), { filePath: SCREEN });
    expect(restricted(responsive?.messages ?? []).length).toBeGreaterThan(0);
  });

  it("when enabled, leaves colour and alignment utilities alone", async () => {
    const enabled = await withDeferredSet();
    const [result] = await enabled.lintText(cls("text-ink-2 text-left text-center text-muted"), {
      filePath: SCREEN,
    });
    expect(restricted(result?.messages ?? [])).toEqual([]);
  });
});

describe("SPEC-048 ac5 formatting and the clock", () => {
  it("rejects toLocaleDateString", async () => {
    const found = await violations(
      "export const d = (x: Date) => x.toLocaleDateString('en-US');",
      SCREEN,
    );
    expect(found.length).toBeGreaterThan(0);
  });

  it.each([
    "export const d = (x: Date) => x.toLocaleString();",
    "export const d = (x: Date) => x.toLocaleTimeString();",
    "export const d = (x: number) => x.toLocaleString('en-US');",
    "export const d = (x: number) => x.toFixed(2);",
    "export const d = (x: number) => new Intl.NumberFormat('en-US').format(x);",
    "export const d = (x: Date) => Intl.DateTimeFormat().format(x);",
    "export const d = () => Date.now();",
  ])("rejects outside format.ts and clock.tsx: %s", async (code) => {
    expect((await violations(code, SCREEN)).length, code).toBeGreaterThan(0);
    expect((await violations(code, "src/lib/other.ts")).length, code).toBeGreaterThan(0);
  });

  it("allows toLocale*, Intl and toFixed in format.ts, and Date.now() in clock.tsx", async () => {
    const fmt =
      "export const f = (x: number, d: Date) => [x.toFixed(2), x.toLocaleString(), d.toLocaleDateString(), new Intl.NumberFormat('en-US').format(x)];";
    expect(await violations(fmt, "src/lib/format.ts")).toEqual([]);
    expect(await violations(fmt, "src/format.ts")).toEqual([]);
    const clock = "export const now = () => Date.now();";
    expect(await violations(clock, "src/lib/clock.tsx")).toEqual([]);
    expect(await violations(clock, "src/clock.tsx")).toEqual([]);
  });

  it("keeps the other bans inside format.ts and clock.tsx", async () => {
    const now = "export const d = () => Date.now();";
    const fixed = "export const d = (x: number) => x.toFixed(2);";
    expect((await violations(now, "src/lib/format.ts")).length).toBeGreaterThan(0);
    expect((await violations(fixed, "src/lib/clock.tsx")).length).toBeGreaterThan(0);
    expect(
      (await violations("export const x = fetch('/v1/me');", "src/lib/format.ts")).length,
    ).toBeGreaterThan(0);
  });

  it("applies in packages/ui too", async () => {
    const fixed = "export const d = (x: number) => x.toFixed(2);";
    expect((await uiViolations(fixed, "src/components/a.tsx")).length).toBeGreaterThan(0);
    expect(await uiViolations(fixed, "src/format.ts")).toEqual([]);
    const now = "export const d = () => Date.now();";
    expect((await uiViolations(now, "src/components/a.tsx")).length).toBeGreaterThan(0);
  });

  it("skips test files, and does not object to other Date and Number use", async () => {
    expect(await violations("export const d = () => Date.now();", "src/lib/x.test.ts")).toEqual(
      [],
    );
    const ok =
      "export const d = (x: string) => [new Date(x), Date.parse(x), Number(x), x.length.toString()];";
    expect(await violations(ok, SCREEN)).toEqual([]);
  });
});

describe("SPEC-048 ac5 L1 brand strings", () => {
  it("rejects Accrual in strings, templates and JSX text", async () => {
    for (const code of [
      'export const t = "Accrual";',
      "export const t = `Welcome to Accrual`;",
      "export const A = () => <h1>Accrual</h1>;",
      'export const A = () => <img alt="Accrual logo" />;',
    ]) {
      expect((await violations(code, SCREEN)).length, code).toBeGreaterThan(0);
    }
  });

  it("accepts Accrued and ordinary accounting words", async () => {
    const code =
      'export const t = ["Accrued", "accrual basis", "accruals", "Accrued Agent"];\nexport const A = () => <h1>Accrued</h1>;';
    expect(await violations(code, SCREEN)).toEqual([]);
  });

  it.each([
    [0x1f680],
    [0x1f600],
    [0x2705],
    [0x274c],
    [0x2b50],
    [0x26a1],
    [0x1f1fa, 0x1f1f8],
    [0x2764, 0xfe0f],
  ])("rejects the emoji %j in strings and JSX text", async (...points) => {
    const char = String.fromCodePoint(...points);
    expect((await violations(`export const t = "Done ${char}";`, SCREEN)).length).toBeGreaterThan(
      0,
    );
    expect(
      (await violations(`export const A = () => <p>Done ${char}</p>;`, SCREEN)).length,
    ).toBeGreaterThan(0);
  });

  it("accepts the typographic characters the product uses", async () => {
    const chars = [0x2013, 0x2014, 0x2192, 0x2022, 0xa9, 0x2713, 0x2026, 0xb7, 0x2212, 0x2318]
      .map((p) => String.fromCodePoint(p))
      .join(" ");
    expect(await violations(`export const t = "${chars}";`, SCREEN)).toEqual([]);
  });

  it("applies in packages/ui and skips tests", async () => {
    expect(
      (await uiViolations('export const t = "Accrual";', "src/components/a.tsx")).length,
    ).toBeGreaterThan(0);
    expect(await violations('export const t = "Accrual";', "src/legacy/Example.test.tsx")).toEqual(
      [],
    );
  });
});

describe("SPEC-048 ac5 the design rules extend, never weaken, the architecture rules", () => {
  it("still reports dangerouslySetInnerHTML beside a palette class", async () => {
    const found = await violations(
      'export const A = ({ h }: { h: string }) => <p className="bg-neutral-100" dangerouslySetInnerHTML={{ __html: h }} />;',
      SCREEN,
    );
    expect(found.some((m) => m.includes("Never render HTML"))).toBe(true);
    expect(found.some((m) => m.includes("design tokens"))).toBe(true);
  });

  it("packages/ui keeps its fetch and HTML bans", async () => {
    expect(
      (await uiViolations("export const x = fetch('/');", "src/components/a.tsx")).length,
    ).toBeGreaterThan(0);
    const html = "export const f = (e: HTMLElement) => { e.innerHTML = 'x'; };";
    expect((await uiViolations(html, "src/components/a.tsx")).length).toBeGreaterThan(0);
  });
});
