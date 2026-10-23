// @vitest-environment node
// F-05-T62: independent acceptance tests (ADR-078) for the CI frontend job (F-05-T17), written
// from the acceptance criteria: "an over-budget firm, portal or route chunk fails, and each
// compiled-CSS rule rejects its deny case, and they pass unedited on main." Black-box: each case
// builds a throwaway dist directory and runs the real stage 1 script as `make check-fast` does
// (`node scripts/bundle-budget.mjs dist`, `node scripts/check-compiled-css.js dist`), asserting on
// the exit code and the line it prints. The path-filter half ("a frontend-only diff skips backend
// shards") is backend/tests/unit/tools/test_f05t62_ci_frontend_independent.py.
import { afterAll, describe, expect, it } from "vitest";

interface Proc {
  status: number | null;
  stdout: string;
  stderr: string;
}
type Spawn = (cmd: string, args: string[], opts: { cwd: string; encoding: "utf8" }) => Proc;
interface Fs {
  mkdtempSync: (prefix: string) => string;
  mkdirSync: (path: string, opts: { recursive: boolean }) => void;
  writeFileSync: (path: string, data: string | Uint8Array) => void;
  rmSync: (path: string, opts: { recursive: boolean; force: boolean }) => void;
}

const node = (globalThis as unknown as { process: { cwd: () => string; execPath: string } })
  .process;
const load = async <T>(name: string): Promise<T> => (await import(/* @vite-ignore */ name)) as T;
const { spawnSync } = await load<{ spawnSync: Spawn }>("node:child_process");
const fs = await load<Fs>("node:fs");
const { tmpdir } = await load<{ tmpdir: () => string }>("node:os");
const { randomBytes } = await load<{ randomBytes: (n: number) => Uint8Array }>("node:crypto");

const APP = node.cwd();
const made: string[] = [];
afterAll(() => {
  for (const dir of made) fs.rmSync(dir, { recursive: true, force: true });
});

function dist(): string {
  const dir = fs.mkdtempSync(`${tmpdir()}/f05-t62-`);
  made.push(dir);
  fs.mkdirSync(`${dir}/assets`, { recursive: true });
  fs.mkdirSync(`${dir}/.vite`, { recursive: true });
  return dir;
}

function run(script: string, dir: string): Proc {
  return spawnSync(node.execPath, [`scripts/${script}`, dir], { cwd: APP, encoding: "utf8" });
}

// ---- Bundle budgets ---------------------------------------------------------------------------------

const KB = 1000;

interface Chunk {
  file: string;
  isEntry?: boolean;
  isDynamicEntry?: boolean;
  imports?: string[];
}

/** A build whose JS files are random bytes of the given sizes: gzip cannot shrink them, so each
 * file's gzip size is about its size (plus a few bytes of framing). */
function build(manifest: Record<string, Chunk & { kb: number }>): string {
  const dir = dist();
  const out: Record<string, Chunk> = {};
  for (const [key, { kb, ...chunk }] of Object.entries(manifest)) {
    fs.writeFileSync(`${dir}/${chunk.file}`, randomBytes(Math.round(kb * KB)));
    out[key] = chunk;
  }
  fs.writeFileSync(`${dir}/.vite/manifest.json`, JSON.stringify(out));
  return dir;
}

describe("bundle budgets: firm 250 KB, portal 150 KB, route chunk 120 KB (gzip)", () => {
  it("a build inside every budget passes", () => {
    const r = run(
      "bundle-budget.mjs",
      build({
        "index.html": { file: "assets/index.js", isEntry: true, imports: ["_v.js"], kb: 150 },
        "_v.js": { file: "assets/v.js", kb: 80 },
        "src/screens/A.tsx": { file: "assets/A.js", isDynamicEntry: true, kb: 100 },
      }),
    );
    expect(r.status).toBe(0);
    expect(r.stdout).toContain("budgets met");
  });

  it("a firm entry over 250 KB fails, counting the chunks it imports statically", () => {
    const r = run(
      "bundle-budget.mjs",
      build({
        "index.html": { file: "assets/index.js", isEntry: true, imports: ["_v.js"], kb: 180 },
        "_v.js": { file: "assets/v.js", kb: 80 },
      }),
    );
    expect(r.status).toBe(1);
    expect(r.stdout).toMatch(/^OVER .*firm initial/m);
  });

  it("a portal entry over 150 KB fails", () => {
    const r = run(
      "bundle-budget.mjs",
      build({
        "index.html": { file: "assets/index.js", isEntry: true, kb: 100 },
        "portal.html": { file: "assets/portal.js", isEntry: true, kb: 160 },
      }),
    );
    expect(r.status).toBe(1);
    expect(r.stdout).toMatch(/^OVER .*portal initial/m);
  });

  it("a route chunk over 120 KB fails, counting what it adds to the initial load", () => {
    const r = run(
      "bundle-budget.mjs",
      build({
        "index.html": { file: "assets/index.js", isEntry: true, kb: 100 },
        "src/screens/B.tsx": {
          file: "assets/B.js",
          isDynamicEntry: true,
          imports: ["_big.js"],
          kb: 70,
        },
        "_big.js": { file: "assets/big.js", kb: 60 },
      }),
    );
    expect(r.status).toBe(1);
    expect(r.stdout).toMatch(/^OVER .*route src\/screens\/B\.tsx/m);
  });

  it("a build with no manifest fails rather than passing unmeasured", () => {
    const dir = dist();
    expect(run("bundle-budget.mjs", dir).status).toBe(1);
  });
});

// ---- Compiled CSS -------------------------------------------------------------------------------

function css(text: string): Proc {
  const dir = dist();
  fs.writeFileSync(`${dir}/assets/index.css`, text);
  return run("check-compiled-css.js", dir);
}

describe("compiled-CSS rules, each with its deny case", () => {
  it("a clean sheet of tokens and 400/500 weights passes", () => {
    const r = css(".a{color:#2b1f17;font-weight:500}.b{background:#fff;font-weight:400}");
    expect(r.status).toBe(0);
  });

  it("a weight of 600 or above outside [data-doc] fails", () => {
    for (const weight of ["600", "700", "bold"]) {
      const r = css(`.a{font-weight:${weight}}`);
      expect(r.status, weight).toBe(1);
    }
  });

  it("the same weight inside a [data-doc] rule passes", () => {
    expect(css("[data-doc] .a{font-weight:700}").status).toBe(0);
  });

  it("a colour literal that is not a token fails, in a property or inside a shadow", () => {
    expect(css(".a{color:#123456}").status).toBe(1);
    expect(css(".a{box-shadow:0 1px 2px rgba(0,0,255,.5)}").status).toBe(1);
    expect(css(".a{color:oklch(60% .2 250)}").status).toBe(1);
  });

  it("a handoff reference colour fails outside [data-contrast=reference] and passes inside", () => {
    // The handoff's match ink, #9253A2; the shipped token is the AA #7E4590 (contrast.css).
    expect(css(".a{color:#9253a2}").status).toBe(1);
    expect(css('[data-contrast="reference"]{--color-match-ink:#9253a2}').status).toBe(0);
  });

  it("the espresso ink at another opacity is the same token, as Tailwind's modifiers write it", () => {
    expect(css(".a{color:rgba(43,31,23,.62)}").status).toBe(0);
  });

  it("a build with no stylesheet fails rather than passing unchecked", () => {
    expect(run("check-compiled-css.js", dist()).status).toBe(1);
  });
});
