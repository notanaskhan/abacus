// The visual-parity harness's shared pieces (F-05-T16; chapter 04 §9.3, F-05 §3.I2).
import { readFileSync, writeFileSync } from "node:fs";
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

/** A gallery screen page (`screens/SHL-01?st=a`) under the same parameters as the index. */
export function screenUrl(path: string): string {
  const [route = "", query] = path.split("?");
  return `/components/${route}?frame=1&static=1&contrast=reference${query === undefined ? "" : `&${query}`}`;
}

/** The gallery index, or one of its screen pages (`screens/SHL-01?st=a`; P-01-T02). */
export async function openGallery(page: Page, path?: string): Promise<void> {
  await page.clock.setFixedTime(FIXED_TIME);
  await page.goto(path === undefined ? GALLERY_URL : screenUrl(path));
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
  /** A gallery screen page instead of the specimen index (`screens/SHL-01?st=a`); `selector` is
   * then a CSS selector on that page. */
  page?: string;
  source: string;
  tier: "A" | "B" | "C" | "D";
  locked?: boolean;
  deviation?: string;
  /** CSS selectors inside the shot whose boxes are painted out of both the render and the handoff
   * baseline before they are compared (chapter 04's parity harness masks: spinners, presence
   * avatars, upload bars, missing icons; a screen's dock until P-09 locks SHL-13). */
  mask?: string[];
  /** A chrome strip inside the frame (F-06 §5.4 Tier A: envelope header 46, steps pane 300, the
   * 64 px document rows, sticky bars): the entry shoots the whole frame like its window entry,
   * then compares only the strip's box, cut from the render and from the frame's own baseline, so a
   * strip needs no hand-measured crop and never drifts from the frame it sits in (F-06-T13). */
  strip?: string;
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

/**
 * A screenshot of exactly the element's own box. An element at a fractional page offset (the
 * gallery stacks specimens whose text lines are fractional, so a frame can sit at y 19.875) is shot
 * by `locator.screenshot()` with its box rounded outward: a 860-high window comes back 1722 device
 * pixels high against a 1720 baseline, and the size check fails before any pixel is compared
 * (F-05-T49). Rounding the box's origin to the nearest CSS pixel keeps its own width and height.
 */
export async function shootWhole(page: Page, target: Locator): Promise<Buffer> {
  const box = await target.boundingBox();
  const viewport = page.viewportSize();
  // A box that does not fit the viewport is shot the usual way (the size check then says so).
  if (
    box === null ||
    viewport === null ||
    box.y < 0 ||
    Math.round(box.y) + Math.round(box.height) > viewport.height
  )
    return target.screenshot({ animations: "disabled", caret: "hide" });
  return page.screenshot({
    animations: "disabled",
    caret: "hide",
    clip: {
      x: Math.round(box.x),
      y: Math.round(box.y),
      width: Math.round(box.width),
      height: Math.round(box.height),
    },
  });
}

/** A PNG's pixel size, from its IHDR chunk. */
export function pngSize(png: Uint8Array): { width: number; height: number } {
  const view = new DataView(png.buffer, png.byteOffset, png.byteLength);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

/** A rectangle in a shot's device pixels. */
export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** The colour a mask paints: opaque, and in no Accrued token, so it never matches by chance. */
export const MASK_COLOUR = "#ff00ff";

/** The boxes of `selectors` inside `target`, in the device pixels of `shot` (the target's own
 * screenshot), so the same boxes can be painted on the shot and on its baseline. */
export async function maskBoxes(
  target: Locator,
  selectors: string[],
  shot: Uint8Array,
): Promise<Box[]> {
  const frame = await target.boundingBox();
  if (frame === null) return [];
  const scale = pngSize(shot).width / Math.round(frame.width);
  const boxes: Box[] = [];
  for (const selector of selectors) {
    for (const part of await target.locator(selector).all()) {
      const box = await part.boundingBox();
      if (box === null) continue;
      boxes.push({
        x: Math.round((box.x - Math.round(frame.x)) * scale),
        y: Math.round((box.y - Math.round(frame.y)) * scale),
        width: Math.round(box.width * scale),
        height: Math.round(box.height * scale),
      });
    }
  }
  return boxes;
}

/** `png` with `boxes` filled in MASK_COLOUR, drawn on a blank page's canvas (no app CSP, and no
 * PNG library: chapter 04 keeps the comparator Playwright's own). */
function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

// A Buffer, not a bare Uint8Array: Playwright's toMatchSnapshot refuses anything else.
function fromBase64(text: string): Buffer {
  return Buffer.from(Uint8Array.from(atob(text), (c) => c.charCodeAt(0)));
}

export async function paintBoxes(page: Page, png: Uint8Array, boxes: Box[]): Promise<Uint8Array> {
  if (boxes.length === 0) return png;
  const scratch = await page.context().newPage();
  try {
    const painted = await scratch.evaluate(
      async ({ data, rects, colour }) => {
        const image = new Image();
        image.src = `data:image/png;base64,${data}`;
        await image.decode();
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const context = canvas.getContext("2d");
        if (context === null) throw new Error("no 2d canvas");
        context.drawImage(image, 0, 0);
        context.fillStyle = colour;
        for (const r of rects) context.fillRect(r.x, r.y, r.width, r.height);
        return canvas.toDataURL("image/png").slice("data:image/png;base64,".length);
      },
      { data: toBase64(png), rects: boxes, colour: MASK_COLOUR },
    );
    return fromBase64(painted);
  } finally {
    await scratch.close();
  }
}

/**
 * For an entry with masks: the render and its baseline with the same boxes painted out, the
 * painted baseline written beside the original (`<name>.masked.png`, never committed: `.visual` is
 * local) and that name to compare against. Without masks, the shot and its own name unchanged.
 */
export async function masked(
  page: Page,
  target: Locator,
  selectors: string[] | undefined,
  shot: Uint8Array,
  name: string,
  snapshotPath: (name: string) => string,
): Promise<{ actual: Uint8Array; name: string }> {
  if (selectors === undefined || selectors.length === 0) return { actual: shot, name };
  const boxes = await maskBoxes(target, selectors, shot);
  const maskedName = name.replace(/\.png$/u, ".masked.png");
  const baseline = await paintBoxes(page, readFileSync(snapshotPath(name)), boxes);
  writeFileSync(snapshotPath(maskedName), baseline);
  return { actual: await paintBoxes(page, shot, boxes), name: maskedName };
}

/** `png` cut to `box` (device pixels), on a blank page's canvas like `paintBoxes`. */
export async function cropPng(page: Page, png: Uint8Array, box: Box): Promise<Buffer> {
  const scratch = await page.context().newPage();
  try {
    const cut = await scratch.evaluate(
      async ({ data, r }) => {
        const image = new Image();
        image.src = `data:image/png;base64,${data}`;
        await image.decode();
        const canvas = document.createElement("canvas");
        canvas.width = r.width;
        canvas.height = r.height;
        const context = canvas.getContext("2d");
        if (context === null) throw new Error("no 2d canvas");
        context.drawImage(image, r.x, r.y, r.width, r.height, 0, 0, r.width, r.height);
        return canvas.toDataURL("image/png").slice("data:image/png;base64,".length);
      },
      { data: toBase64(png), r: box },
    );
    return fromBase64(cut);
  } finally {
    await scratch.close();
  }
}

/**
 * For an entry with a `strip`: the strip's box cut from the (masked) render and from its
 * (masked) baseline, the cut baseline written beside it (`<name>.strip.png`, local only) and that
 * name to compare against. A strip that does not render is an error, never a pass. Without a
 * strip, the shot and its name unchanged.
 */
export async function stripped(
  page: Page,
  target: Locator,
  strip: string | undefined,
  shot: { actual: Uint8Array; name: string },
  snapshotPath: (name: string) => string,
): Promise<{ actual: Uint8Array; name: string }> {
  if (strip === undefined) return shot;
  const [box] = await maskBoxes(target, [strip], shot.actual);
  if (box === undefined) throw new Error(`strip ${strip} is not in the frame`);
  const name = shot.name.replace(/(\.masked)?\.png$/u, ".strip.png");
  const baseline = await cropPng(page, readFileSync(snapshotPath(shot.name)), box);
  writeFileSync(snapshotPath(name), baseline);
  return { actual: await cropPng(page, shot.actual, box), name };
}
