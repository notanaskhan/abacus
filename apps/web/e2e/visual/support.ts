// The visual-parity harness's shared pieces (F-05-T16; chapter 04 §9.3, F-05 §3.I2).
import { readFileSync } from "node:fs";
import { type Locator, type Page } from "@playwright/test";

/** The gallery as the harness renders it: no chrome, frozen, the handoff's ink ladder. */
export const GALLERY_URL = "/components?frame=1&static=1&contrast=reference";

/** The clock every parity render runs on: the seed's E0 instant (chapter 04 §9.3). */
export const FIXED_TIME = new Date("2026-09-14T09:24:00-05:00");

/** Tier tolerances (chapter 04 §9.3; calibrated in F-05-T16, see work/tasks/TASK-341). */
export const TIERS = {
  A: { threshold: 0.1, maxDiffPixelRatio: 0.005 },
  B: { threshold: 0.15, maxDiffPixelRatio: 0.02 },
  C: { threshold: 0.2, maxDiffPixelRatio: 0.03 },
} as const;
export type PixelTier = keyof typeof TIERS;

export async function openGallery(page: Page): Promise<void> {
  await page.clock.setFixedTime(FIXED_TIME);
  await page.goto(GALLERY_URL);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

/** A specimen's section on the gallery page, or a part of it (a CSS selector inside it). */
export function specimen(page: Page, id: string, selector?: string): Locator {
  const section = page.locator(`section[id="${id}"]`);
  return selector === undefined ? section : section.locator(selector);
}

export interface ManifestEntry {
  selector?: string;
  source: string;
  tier: "A" | "B" | "C" | "D";
  locked?: boolean;
  deviation?: string;
}

/** The checked-in manifest (docs/design/parity-manifest.json), read from apps/web. */
export function readManifest(): Record<string, ManifestEntry> {
  const raw = JSON.parse(readFileSync("../../docs/design/parity-manifest.json", "utf8")) as {
    entries: Record<string, ManifestEntry>;
  };
  return raw.entries;
}

export function readHandoffVersion(): string {
  return readFileSync("../../docs/design/HANDOFF_VERSION", "utf8").trim();
}

/** The specimen a manifest key belongs to: `c-06-tick.ms` is on `c-06-tick`. */
export function specimenOf(key: string): string {
  return key.split(".")[0] ?? key;
}

/** A PNG's pixel size, from its IHDR chunk. */
export function pngSize(png: Uint8Array): { width: number; height: number } {
  const view = new DataView(png.buffer, png.byteOffset, png.byteLength);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}
