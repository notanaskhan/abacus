// ac-test-author: ayushkbhatia
// @vitest-environment node
// P-08-T22 (ADR-078), for P-08-T07: the portal build's CSP and import boundaries, from ADR-163
// §1, §4 and §6, P-08 §5.2 and Story 1.1, and the T07 acceptance ("vite build --mode portal emits
// dist/portal with no firm chunk"). Behaviour, not source text: the CSP is the one the resolved
// `--mode portal` build config actually injects, and the boundary is the static import graph
// walked from the portal entry.
import { describe, expect, it } from "vitest";
import { WEB, exists, read } from "../lint/ui-files";

interface HtmlTag {
  tag: string;
  attrs?: Record<string, string>;
}
interface BuildPlugin {
  name?: string;
  transformIndexHtml?: unknown;
}
interface ResolvedConfig {
  plugins?: unknown[];
  build?: { outDir?: string; rollupOptions?: { input?: unknown } };
}
type ConfigFn = (env: {
  mode: string;
  command: "build" | "serve";
  isSsrBuild: boolean;
  isPreview: boolean;
}) => ResolvedConfig;

async function portalBuildConfig(): Promise<ResolvedConfig> {
  const loaded = (await import("../../vite.config")) as { default: unknown };
  const config = loaded.default;
  expect(typeof config).toBe("function");
  return (config as ConfigFn)({
    mode: "portal",
    command: "build",
    isSsrBuild: false,
    isPreview: false,
  });
}

/** The Content-Security-Policy the build writes into portal.html, as directive -> sources. */
async function portalCsp(): Promise<Map<string, string[]>> {
  const config = await portalBuildConfig();
  const plugins = (config.plugins ?? []).flat(3) as BuildPlugin[];
  const tags: HtmlTag[] = [];
  for (const plugin of plugins) {
    const hook = plugin.transformIndexHtml;
    const handler =
      typeof hook === "function" ? hook : (hook as { handler?: unknown } | undefined)?.handler;
    if (typeof handler !== "function") continue;
    const out: unknown = await (handler as (html: string, ctx: object) => unknown)(
      "<html><head></head></html>",
      { path: "/portal.html", filename: `${WEB}/portal.html` },
    );
    if (Array.isArray(out)) tags.push(...(out as HtmlTag[]));
  }
  const metas = tags.filter(
    (t) => t.tag === "meta" && t.attrs?.["http-equiv"] === "Content-Security-Policy",
  );
  expect(metas).toHaveLength(1);
  const policy = new Map<string, string[]>();
  for (const part of (metas[0]?.attrs?.content ?? "").split(";")) {
    const [name, ...sources] = part.trim().split(/\s+/);
    if (name) policy.set(name, sources);
  }
  return policy;
}

const REMOTE = /^(https?:|wss?:|\*|[a-z0-9.-]+\.[a-z]{2,})/i;

describe("P-08-T22 the portal build's CSP (ADR-163 §4, §6)", () => {
  it("builds portal.html alone into dist/portal", async () => {
    const config = await portalBuildConfig();
    expect(config.build?.outDir).toBe("dist/portal");
    expect(config.build?.rollupOptions?.input).toBe("portal.html");
  });

  it("keeps the network to this origin: connect-src 'self' and nothing else", async () => {
    const csp = await portalCsp();
    expect(csp.get("connect-src")).toEqual(["'self'"]);
    expect(csp.get("default-src")).toEqual(["'self'"]);
  });

  it("runs only this origin's scripts, never inline or eval", async () => {
    const csp = await portalCsp();
    expect(csp.get("script-src")).toEqual(["'self'"]);
    for (const [name, sources] of csp) {
      expect(sources, name).not.toContain("'unsafe-inline'");
      expect(sources, name).not.toContain("'unsafe-eval'");
    }
  });

  it("loads images from this origin (the re-encoded logo) and no remote host", async () => {
    const csp = await portalCsp();
    const img = csp.get("img-src") ?? [];
    expect(img).toContain("'self'");
    expect(img.filter((s) => REMOTE.test(s))).toEqual([]);
  });

  it("can't be framed, embed plugins or rebase", async () => {
    const csp = await portalCsp();
    expect(csp.get("frame-ancestors")).toEqual(["'none'"]);
    expect(csp.get("object-src")).toEqual(["'none'"]);
    expect(csp.get("base-uri")).toEqual(["'none'"]);
  });
});

// --- the import boundary (INV-4; ADR-163 §1: the portal bundle has no firm-app chunk) ----------

const IMPORT =
  /(?:import|export)\s[^'"]*?from\s*["']([^"']+)["']|import\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;

interface Graph {
  statically: Set<string>;
  lazily: Set<string>;
}

async function resolveFrom(from: string, spec: string): Promise<string | null> {
  if (!spec.startsWith(".")) return null;
  const dir = from.split("/").slice(0, -1).join("/");
  const parts: string[] = [];
  for (const piece of `${dir}/${spec}`.split("/")) {
    if (piece === "..") parts.pop();
    else if (piece !== "." && piece !== "") parts.push(piece);
  }
  const base = parts.join("/");
  for (const candidate of [
    `${base}.ts`,
    `${base}.tsx`,
    `${base}/index.ts`,
    `${base}/index.tsx`,
    base,
  ]) {
    if (/\.(ts|tsx|css)$/.test(candidate) && (await exists(`${WEB}/${candidate}`))) {
      return candidate;
    }
  }
  return null;
}

/** Every module reached from the portal entry by static imports, and those only lazily. */
async function portalGraph(): Promise<Graph> {
  const statically = new Set<string>();
  const lazily = new Set<string>();
  const queue: [string, boolean][] = [["src/entries/portal.tsx", false]];
  while (queue.length > 0) {
    const [file, lazy] = queue.shift() as [string, boolean];
    const known = lazy ? lazily : statically;
    if (known.has(file) || (lazy && statically.has(file))) continue;
    known.add(file);
    if (file.endsWith(".css")) continue;
    const source = await read(`${WEB}/${file}`);
    for (const match of source.matchAll(IMPORT)) {
      const dynamic = match[3] !== undefined;
      const spec = match[1] ?? match[2] ?? match[3] ?? "";
      const target = await resolveFrom(file, spec);
      if (target !== null) queue.push([target, lazy || dynamic]);
    }
  }
  for (const file of statically) lazily.delete(file);
  return { statically, lazily };
}

const FIRM = [
  /^src\/shell\//, // the firm shell (the portal has PortalLayout)
  /^src\/routes\/(?!portal\/)/, // the firm's routes and root layout
  /^src\/screens\/(?!POR-)/, // a firm screen
  /^src\/legacy\//, // the firm bundle's legacy screens
  /^src\/gallery\//, // the component gallery's specimens
  /^src\/main\.tsx$/, // the firm entry
];

describe("P-08-T22 the portal's import boundary (INV-4, ADR-163 §1, F-05 L7)", () => {
  it("reaches no firm module from the portal entry, eagerly or lazily", async () => {
    const graph = await portalGraph();
    expect(graph.statically.size).toBeGreaterThan(5);
    const reached = [...graph.statically, ...graph.lazily];
    expect(reached.filter((file) => FIRM.some((rule) => rule.test(file)))).toEqual([]);
  });

  it("reaches the fixture seed only lazily, so a production build can drop it", async () => {
    const graph = await portalGraph();
    expect([...graph.statically].filter((file) => file.startsWith("src/fixtures/"))).toEqual([]);
  });

  it("the judgement catches a planted firm import", () => {
    const planted = ["src/screens/POR-02/index.tsx", "src/screens/CLI-01/index.tsx"];
    expect(planted.filter((file) => FIRM.some((rule) => rule.test(file)))).toEqual([
      "src/screens/CLI-01/index.tsx",
    ]);
  });
});
