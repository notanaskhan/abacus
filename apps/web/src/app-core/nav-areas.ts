import { NAV } from "../shell/nav";

// The firm's 13 areas (P-01-T02; SHL-01 b, f, g; chapter 04 §2.2): the registry the toolbar, the
// area routes and the SHL screens share, so it sits in app-core beside the overlay registry. The
// labels and their order are nav.ts's (F-02-T09, D4); this adds, per label, the landing screen
// the item opens (SHL-01 frame b), the area's path, and its G-chord (SHL-03's shortcut list).
//
// Which item is lit: the open screen's manifest `navArea` when the caller knows the screen (an
// artboard), else the area whose path the URL sits in; settings light nothing (SHL-01f). This file
// ships in the production bundle, so it does not import the route manifest (its handoff names
// would ship with it, which the dist test forbids); SHL-01.test.tsx holds the two in step: each
// landing's path and `navArea`, and every routed screen's `navArea` against `activeArea`.

export interface Area {
  label: string;
  /** The landing screen's ID (SHL-01 frame b: Home→HOME-01 … Signatures→SIG-01). */
  landing: string;
  /** The landing's path: the screen's route once it has one, else the area's flag-off page. */
  path: string;
  /** The landing screen has a route (legacy or built); false shows the flag-off page. */
  routed: boolean;
  /** The key after G (G H, G T, G A, G C, G W). */
  chord?: string;
}

const AREA_DATA: Readonly<Record<string, Omit<Area, "label">>> = {
  Home: { landing: "HOME-01", path: "/home", routed: true, chord: "h" },
  Engagements: { landing: "ENG-01", path: "/engagements", routed: true },
  "Tax Returns": { landing: "TAX-01", path: "/tax-returns", routed: false, chord: "t" },
  Files: { landing: "FIL-01", path: "/files", routed: true },
  Knowledge: { landing: "KNW-01", path: "/knowledge", routed: true },
  Workbench: { landing: "WB-01", path: "/workbench", routed: false, chord: "w" },
  Inbox: { landing: "INB-01", path: "/inbox", routed: false },
  Clients: { landing: "CLI-01", path: "/clients", routed: true },
  Binders: { landing: "BND-01", path: "/binders", routed: true },
  Notices: { landing: "NOT-01", path: "/notices", routed: false },
  Audits: { landing: "AUD-01", path: "/audits", routed: true, chord: "a" },
  Closes: { landing: "CLS-01", path: "/closes", routed: false, chord: "c" },
  Signatures: { landing: "SIG-01", path: "/signatures", routed: false },
};

/** The 13 areas, in nav.ts's order. */
export const AREAS: readonly Area[] = NAV.map(({ label }) => {
  const data = AREA_DATA[label];
  if (data === undefined) throw new Error(`nav.ts item "${label}" has no area`);
  return { label, ...data };
});

export function areaByLabel(label: string): Area | undefined {
  return AREAS.find((a) => a.label === label);
}

export function areaByChord(key: string): Area | undefined {
  return AREAS.find((a) => a.chord === key);
}

/** Where the toolbar is: the URL, or the open screen and its manifest `navArea`. */
export interface ToolbarContext {
  pathname?: string;
  screen?: string;
  navArea?: string | undefined;
}

const SETTINGS = /^\/(settings|admin)(\/|$)/;

/** Settings context (SHL-01f): no item lit and the firm pill pressed. */
export function isSettings(context: ToolbarContext): boolean {
  if (context.screen !== undefined) return context.screen.startsWith("ADM-");
  return SETTINGS.test(context.pathname ?? "");
}

function segments(path: string): string[] {
  return path.split("/").filter(Boolean);
}

/** The label of the lit nav item, or "" for none (settings, or a path outside every area). */
export function activeArea(context: ToolbarContext): string {
  if (isSettings(context)) return "";
  if (context.screen !== undefined) return context.navArea ?? "";
  const have = segments(context.pathname ?? "/");
  // "/" redirects to Home's "/home" (I-01-T13), so both light Home.
  if (have.length === 0) return "Home";
  const area = AREAS.find((a) => {
    const want = segments(a.path);
    return want.length > 0 && want.every((w, i) => w === have[i]);
  });
  return area?.label ?? "";
}
