// F-05-T22: independent acceptance tests (ADR-078) for the ?ov= round trip, written from F-05 E1
// ("Given ?ov=request:new, when the page reloads, then the drawer reopens; when Back is pressed,
// then it closes. Never two drawers at once.") and plan 04 §2.4. A reload is a decode of the same
// search value; Back is the previous value. The browser-level E1 checks are e2e/e3.spec.ts.
import { describe, expect, it } from "vitest";
import {
  MAX_OVERLAYS,
  type LayerOf,
  type OverlayRef,
  closeRef,
  decodeOverlays,
  encodeOverlays,
  normalizeOverlays,
  openRef,
} from "./overlays";

const layerOf: LayerOf = (key) =>
  ({ request: "drawer", notifications: "drawer", signoff: "modal", "edit-agent": "modal" })[
    key
  ] as "drawer" | "modal" | undefined;

const ref = (key: string, ...args: string[]): OverlayRef => ({ key, args });

describe("?ov= round trip (E1)", () => {
  it("?ov=request:new reopens the same layer after a reload", () => {
    const opened = openRef([], ref("request", "new"), layerOf);
    const url = encodeOverlays(opened);
    expect(url).toBe("request:new");
    // A reload: the router hands the same search value back.
    expect(normalizeOverlays(decodeOverlays(url), layerOf)).toEqual([ref("request", "new")]);
  });

  it("Back closes it: the previous search value names no layer", () => {
    const before = encodeOverlays([]);
    expect(before).toBeUndefined();
    expect(decodeOverlays(before)).toEqual([]);
  });

  it("an id holding a colon survives the trip", () => {
    const opened = [ref("signoff", "aje", "AJE:06", "reviewer")];
    expect(decodeOverlays(encodeOverlays(opened))).toEqual(opened);
  });

  it("a drawer and a modal on top: two layers, drawer first, and back again", () => {
    const one = openRef([], ref("request", "new"), layerOf);
    const two = openRef(one, ref("signoff", "aje", "AJE-06"), layerOf);
    expect(two.map((r) => r.key)).toEqual(["request", "signoff"]);
    expect(two.length).toBeLessThanOrEqual(MAX_OVERLAYS);
    expect(normalizeOverlays(decodeOverlays(encodeOverlays(two)), layerOf)).toEqual(two);
    // Escape closes the topmost.
    expect(closeRef(two, two.length - 1)).toEqual(one);
  });

  it("never two drawers: a second drawer replaces the first", () => {
    const one = openRef([], ref("request", "new"), layerOf);
    const two = openRef(one, ref("notifications"), layerOf);
    expect(two.filter((r) => layerOf(r.key) === "drawer")).toEqual([ref("notifications")]);
  });

  it("a hand-edited URL with two drawers still draws one", () => {
    const decoded = decodeOverlays(["request:new", "notifications"]);
    const drawn = normalizeOverlays(decoded, layerOf);
    expect(drawn.filter((r) => layerOf(r.key) === "drawer")).toHaveLength(1);
  });

  it("unknown keys and malformed values open nothing", () => {
    expect(normalizeOverlays(decodeOverlays("nope:1"), layerOf)).toEqual([]);
    expect(decodeOverlays({ evil: true })).toEqual([]);
    expect(decodeOverlays("Request:NEW")).toEqual([]);
  });
});
