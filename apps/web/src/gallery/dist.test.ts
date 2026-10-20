// @vitest-environment node
// F-05-T09 (SPEC-048 AC-10): a production build contains no gallery, specimen or fixture code;
// a build with VITE_UI_GALLERY=1 does, which proves the scan can see it.
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import { afterAll, describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const out: string[] = [];

// Strings only the gallery, its specimens and the token page carry.
const GALLERY_MARKERS = [
  "Components in use",
  "Example requests",
  "Every colour token",
  "No screen is registered",
  "Brightwater",
  "VITE_UI_GALLERY",
];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}

async function bundle(gallery: string | undefined): Promise<string> {
  const outDir = mkdtempSync(join(tmpdir(), "abacus-dist-"));
  out.push(outDir);
  const saved = process.env.VITE_UI_GALLERY;
  if (gallery === undefined) delete process.env.VITE_UI_GALLERY;
  else process.env.VITE_UI_GALLERY = gallery;
  try {
    await build({
      root,
      mode: "production",
      logLevel: "silent",
      build: { outDir, emptyOutDir: true },
    });
  } finally {
    if (saved === undefined) delete process.env.VITE_UI_GALLERY;
    else process.env.VITE_UI_GALLERY = saved;
  }
  return files(outDir)
    .filter((f) => /\.(js|css|html)$/.test(f))
    .map((f) => readFileSync(f, "utf8"))
    .join("\n");
}

afterAll(() => {
  for (const dir of out) rmSync(dir, { recursive: true, force: true });
});

describe("ac10 production dist", () => {
  it("contains no gallery, specimen or fixture strings", async () => {
    const dist = await bundle(undefined);
    for (const marker of GALLERY_MARKERS) {
      expect(dist.includes(marker), `dist contains "${marker}"`).toBe(false);
    }
    expect(dist.includes("/components/tokens")).toBe(false);
    expect(dist.includes("data-contrast")).toBe(false);
  }, 240_000);

  it("contains them when VITE_UI_GALLERY=1 (the scan can see the gallery)", async () => {
    const dist = await bundle("1");
    expect(dist.includes("Components in use")).toBe(true);
    expect(dist.includes("Every colour token")).toBe(true);
  }, 240_000);
});
