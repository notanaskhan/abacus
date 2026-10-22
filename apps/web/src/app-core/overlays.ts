// The ?ov= codec and the overlay registry (F-05-T20; plan 04 section 2.4, E3). An overlay of the
// O2 to O6 grammar opens through one search parameter, so it deep-links, survives a reload and
// closes on Back:
//
//   ?ov=<key>[:<arg>]*          one layer, e.g. ?ov=request:new or ?ov=signoff:aje:AJE-06:reviewer
//   ?ov=<a>&ov=<b>              two layers, at most: one drawer and one modal on top of it
//
// This file is the pure part: encode, decode, and the rule for what opening one more layer does
// ("never two drawers"). The hook that reads and writes the URL and the host that renders the
// layers are in overlay-host.tsx. The registry here is where the epics that own SHL-xx overlays
// add theirs; it starts empty.
import type { ReactNode } from "react";

/** At most one drawer (O2) and one modal on top of it (O3 to O6). */
export const MAX_OVERLAYS = 2;

export interface OverlayRef {
  /** Lower-case kebab: `request`, `signoff`, `edit-agent`. */
  key: string;
  /** What follows the key, split on colons: an id, `new`, a nonce. */
  args: string[];
}

const KEY = /^[a-z][a-z0-9-]*$/;

// A colon or a percent sign inside an argument is written %3A or %25, so an argument can hold an
// id like "A:1" and still split cleanly.
const escapeArg = (arg: string): string => arg.replaceAll("%", "%25").replaceAll(":", "%3A");
const unescapeArg = (arg: string): string => arg.replaceAll("%3A", ":").replaceAll("%25", "%");

export function encodeRef(ref: OverlayRef): string {
  return [ref.key, ...ref.args.map(escapeArg)].join(":");
}

/** The ref a string names, or undefined for anything that is not `key[:arg]*`. */
export function decodeRef(text: string): OverlayRef | undefined {
  const [key, ...args] = text.split(":");
  if (key === undefined || !KEY.test(key)) return undefined;
  return { key, args: args.map(unescapeArg) };
}

export const sameRef = (a: OverlayRef, b: OverlayRef): boolean => encodeRef(a) === encodeRef(b);

/**
 * The layers a search value names. The router hands over a string for one layer, an array for
 * repeated keys, and a number for a bare `?ov=123`; anything else, and anything malformed, is
 * dropped. At most two are kept and the same layer is not listed twice.
 */
export function decodeOverlays(raw: unknown): OverlayRef[] {
  const items: unknown[] = Array.isArray(raw) ? (raw as unknown[]) : [raw];
  const refs: OverlayRef[] = [];
  for (const item of items) {
    const text =
      typeof item === "string" ? item : typeof item === "number" ? String(item) : undefined;
    const ref = text === undefined ? undefined : decodeRef(text);
    if (ref === undefined || refs.some((r) => sameRef(r, ref))) continue;
    refs.push(ref);
    if (refs.length === MAX_OVERLAYS) break;
  }
  return refs;
}

/** The search value for these layers: nothing for none, a string for one, an array for two. */
export function encodeOverlays(refs: readonly OverlayRef[]): string | string[] | undefined {
  const kept = refs.slice(0, MAX_OVERLAYS).map(encodeRef);
  if (kept.length === 0) return undefined;
  const [only] = kept;
  return only !== undefined && kept.length === 1 ? only : kept;
}

// ---- Which layers go together ------------------------------------------------------------------

/** A drawer (O2) or a modal layer (O3 sheet, O4 full sheet, O5 palette, O6 wizard, a dialog). */
export type OverlayLayerClass = "drawer" | "modal";

export type LayerOf = (key: string) => OverlayLayerClass | undefined;

/**
 * Open one more layer. Never two drawers: a second drawer replaces the first (chapter 04 section
 * 2.4, inferred in F-05 O1-O6). One modal on top: a second modal replaces the first. The drawer
 * is listed first, the modal after it. Opening the layer that is already open changes nothing. A
 * key the registry does not know is not opened.
 */
export function openRef(
  current: readonly OverlayRef[],
  next: OverlayRef,
  layerOf: LayerOf,
): OverlayRef[] {
  const layer = layerOf(next.key);
  if (layer === undefined) return [...current];
  if (current.some((r) => sameRef(r, next))) return [...current];
  const keep = current.filter((r) => {
    const l = layerOf(r.key);
    return l !== undefined && l !== layer;
  });
  return layer === "drawer" ? [next, ...keep] : [...keep, next];
}

/** The layers with the one at `index` closed: Escape and the close button close the topmost. */
export function closeRef(current: readonly OverlayRef[], index: number): OverlayRef[] {
  return current.filter((_, i) => i !== index);
}

/** The layers that are known, in the order a host draws them: the drawer, then the modal. */
export function normalizeOverlays(refs: readonly OverlayRef[], layerOf: LayerOf): OverlayRef[] {
  return refs.reduce<OverlayRef[]>((acc, ref) => openRef(acc, ref, layerOf), []);
}

// ---- The registry ------------------------------------------------------------------------------

export interface OverlayRenderProps {
  ref: OverlayRef;
  /** Where the layer is in the URL: 0 is the lower one. */
  index: number;
  /** Close this layer: removes it from the URL with `replace`. */
  close: () => void;
}

export interface OverlayEntry {
  layer: OverlayLayerClass;
  /** The layer, drawn open: a Drawer, SheetModal, FullSheet, Wizard or Dialog whose
   * `onOpenChange(false)` calls `close`. */
  render: (props: OverlayRenderProps) => ReactNode;
}

const registry = new Map<string, OverlayEntry>();

/** Add the layer an epic owns, by its `?ov=` key. Re-registering a key replaces it. */
export function registerOverlay(key: string, entry: OverlayEntry): void {
  registry.set(key, entry);
}

export function overlayEntry(key: string): OverlayEntry | undefined {
  return registry.get(key);
}

export const layerOfKey: LayerOf = (key) => registry.get(key)?.layer;

/** For tests: forget every registered layer. */
export function clearOverlayRegistry(): void {
  registry.clear();
}
