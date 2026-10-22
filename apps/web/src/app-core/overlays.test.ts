// F-05-T20: the ?ov= codec (plan 04 section 2.4): encode, decode, the two-layer limit, and what
// opening one more layer does.
import { afterEach, describe, expect, it } from "vitest";
import {
  MAX_OVERLAYS,
  type OverlayLayerClass,
  clearOverlayRegistry,
  closeRef,
  decodeOverlays,
  decodeRef,
  encodeOverlays,
  encodeRef,
  layerOfKey,
  normalizeOverlays,
  openRef,
  registerOverlay,
} from "./overlays";

const LAYERS: Record<string, OverlayLayerClass> = {
  request: "drawer",
  notifications: "drawer",
  viewer: "drawer",
  signoff: "modal",
  issue: "modal",
  envelope: "modal",
};
const layerOf = (key: string): OverlayLayerClass | undefined => LAYERS[key];
const ref = (key: string, ...args: string[]) => ({ key, args });

afterEach(clearOverlayRegistry);

describe("one layer", () => {
  it("writes the key and its arguments joined by colons", () => {
    expect(encodeRef(ref("notifications"))).toBe("notifications");
    expect(encodeRef(ref("request", "new"))).toBe("request:new");
    expect(encodeRef(ref("signoff", "aje", "AJE-06", "reviewer"))).toBe(
      "signoff:aje:AJE-06:reviewer",
    );
  });

  it("reads them back", () => {
    expect(decodeRef("request:new:n_8f2a")).toEqual(ref("request", "new", "n_8f2a"));
    expect(decodeRef("notifications")).toEqual(ref("notifications"));
  });

  it("round-trips an argument that holds a colon or a percent sign", () => {
    const r = ref("viewer", "ev:1", "100%", "plain");
    expect(encodeRef(r)).toBe("viewer:ev%3A1:100%25:plain");
    expect(decodeRef(encodeRef(r))).toEqual(r);
  });

  it("refuses a key that is not lower-case kebab, so nothing odd reaches the registry", () => {
    for (const bad of ["", ":x", "Request:new", "1abc", "a b", "<script>", "a_b"]) {
      expect(decodeRef(bad), bad).toBeUndefined();
    }
  });
});

describe("the search value", () => {
  it("is nothing for no layer, a string for one and an array for two", () => {
    expect(encodeOverlays([])).toBeUndefined();
    expect(encodeOverlays([ref("request", "new")])).toBe("request:new");
    expect(encodeOverlays([ref("request", "new"), ref("signoff", "aje", "AJE-06")])).toEqual([
      "request:new",
      "signoff:aje:AJE-06",
    ]);
  });

  it("decodes what the router hands over: a string, an array, a number, nothing", () => {
    expect(decodeOverlays("request:new")).toEqual([ref("request", "new")]);
    expect(decodeOverlays(["request:new", "signoff:aje"])).toEqual([
      ref("request", "new"),
      ref("signoff", "aje"),
    ]);
    expect(decodeOverlays(undefined)).toEqual([]);
    expect(decodeOverlays(42)).toEqual([]);
    expect(decodeOverlays({ key: "request" })).toEqual([]);
    expect(decodeOverlays("")).toEqual([]);
  });

  it("round-trips, for one layer and for two", () => {
    for (const refs of [
      [ref("notifications")],
      [ref("request", "new", "n_8f2a"), ref("issue", "new", "03 Liabilities!C29")],
    ]) {
      expect(decodeOverlays(encodeOverlays(refs))).toEqual(refs);
    }
  });

  it("keeps at most two layers, skips what is malformed and does not list one twice", () => {
    expect(MAX_OVERLAYS).toBe(2);
    expect(decodeOverlays(["request:new", "BAD", "request:new", "signoff:a", "issue:b"])).toEqual([
      ref("request", "new"),
      ref("signoff", "a"),
    ]);
    expect(encodeOverlays([ref("a"), ref("b"), ref("c")])).toEqual(["a", "b"]);
  });
});

describe("opening one more layer", () => {
  it("never two drawers: a second drawer replaces the first", () => {
    const next = openRef([ref("request", "new")], ref("notifications"), layerOf);
    expect(next).toEqual([ref("notifications")]);
  });

  it("puts a modal on top of a drawer, and keeps the drawer", () => {
    const next = openRef([ref("request", "new")], ref("signoff", "aje"), layerOf);
    expect(next).toEqual([ref("request", "new"), ref("signoff", "aje")]);
  });

  it("lists a drawer opened over a modal first, so the modal stays on top", () => {
    const next = openRef([ref("signoff", "aje")], ref("request", "new"), layerOf);
    expect(next).toEqual([ref("request", "new"), ref("signoff", "aje")]);
  });

  it("a second modal replaces the first, so there are never more than two layers", () => {
    const next = openRef(
      [ref("request", "new"), ref("signoff", "aje")],
      ref("issue", "new"),
      layerOf,
    );
    expect(next).toEqual([ref("request", "new"), ref("issue", "new")]);
    expect(next.length).toBeLessThanOrEqual(MAX_OVERLAYS);
  });

  it("changes nothing when that layer is open already, or the key is unknown", () => {
    const open = [ref("request", "new")];
    expect(openRef(open, ref("request", "new"), layerOf)).toEqual(open);
    expect(openRef(open, ref("mystery"), layerOf)).toEqual(open);
  });

  it("does not mutate the list it was given", () => {
    const open = [ref("request", "new")];
    openRef(open, ref("signoff", "aje"), layerOf);
    expect(open).toEqual([ref("request", "new")]);
  });
});

describe("closing and normalising", () => {
  it("closes the layer at an index, so Escape takes the topmost", () => {
    const refs = [ref("request", "new"), ref("signoff", "aje")];
    expect(closeRef(refs, 1)).toEqual([ref("request", "new")]);
    expect(closeRef(refs, 0)).toEqual([ref("signoff", "aje")]);
  });

  it("drops keys the registry does not know and repairs a URL with two drawers", () => {
    expect(
      normalizeOverlays([ref("request", "a"), ref("mystery"), ref("notifications")], layerOf),
    ).toEqual([ref("notifications")]);
    expect(normalizeOverlays([ref("signoff", "aje"), ref("request", "new")], layerOf)).toEqual([
      ref("request", "new"),
      ref("signoff", "aje"),
    ]);
  });
});

describe("the registry", () => {
  it("starts empty, takes entries by key and forgets them on clear", () => {
    expect(layerOfKey("request")).toBeUndefined();
    registerOverlay("request", { layer: "drawer", render: () => null });
    expect(layerOfKey("request")).toBe("drawer");
    clearOverlayRegistry();
    expect(layerOfKey("request")).toBeUndefined();
  });
});
