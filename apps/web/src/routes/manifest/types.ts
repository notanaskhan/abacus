// The route registry's entry shape (F-04-T14; chapter 04 section 2.6). One entry per screen ID of
// the design handoff, seeded by scripts/seed-manifest.mjs and then owned by the screen's builder.

/** planned: not built. fixture: built on fixture scenarios. live: built on the real API. */
export type ScreenStatus = "planned" | "fixture" | "live";

export interface ScreenEntry {
  /** The handoff's name for the screen, for reading the manifest. */
  readonly name: string;
  readonly status: ScreenStatus;
  /** The route's full path in the area route tree (`$param` segments), or null until routed. */
  readonly path: string | null;
  /** No designed link targets this screen: it is reached from the bar, a deep link or an email. */
  readonly entry?: true;
  /** The screen's source folder under src/, when it is not `screens/<ID>`. */
  readonly folder?: string;
  /** The nav item (a label of shell/nav.ts) lit while the screen is open (P-01-T02; SHL-01b, g).
   * A screen without one lights nothing of its own: the toolbar falls back to the area its path
   * sits in. Nothing is ever added to the bar for a screen (D4). */
  readonly navArea?: string;
}

export type Manifest = Readonly<Record<string, ScreenEntry>>;
