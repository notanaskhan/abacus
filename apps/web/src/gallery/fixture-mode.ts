import { type ComponentType, useEffect, useState } from "react";

// The pass-through to F-04-T04's fixture mode (SPEC-048 AC-11): the gallery parses the query
// parameters once and hands them to the registered screen. With VITE_FIXTURES=1, the Brightwater
// Hale seed (F-04-T05) answers the generated client under the screen first, as the persona,
// clock and latency the parameters name; a screen's own scenario installs over it. Gallery
// builds only.

export interface FixtureParams {
  /** Artboard state letter (`?st=`). */
  st?: string;
  /** Persona (`?as=`). */
  as?: string;
  /** Frozen clock, ISO 8601 (`?clock=`). */
  clock?: string;
  /** Simulated latency in ms (`?latency=`). */
  latency?: string;
  /** `?frame=1`: the artboard alone, without the gallery's own chrome. */
  frame: boolean;
  /** `?static=1`: no motion, for parity runs. */
  static: boolean;
  /** `?contrast=reference`: the handoff's ink ladder instead of the AA ladder. */
  contrast?: "reference";
}

function text(value: unknown): string | undefined {
  // The router parses `?latency=250` to a number; the screens want the text back.
  return typeof value === "string" || typeof value === "number" ? String(value) : undefined;
}

export function parseFixtureParams(search: Record<string, unknown>): FixtureParams {
  const out: FixtureParams = {
    frame: text(search.frame) === "1",
    static: text(search.static) === "1",
  };
  const st = text(search.st);
  const as = text(search.as);
  const clock = text(search.clock);
  const latency = text(search.latency);
  if (st !== undefined) out.st = st;
  if (as !== undefined) out.as = as;
  if (clock !== undefined) out.clock = clock;
  if (latency !== undefined) out.latency = latency;
  if (text(search.contrast) === "reference") out.contrast = "reference";
  return out;
}

/**
 * Answers the generated client from the interim seed while the page shows. True once it does (at
 * once when fixtures are off), so the screen mounts after, and its own scenario wins over the seed.
 */
export function useSeedFixtures(params: FixtureParams): boolean {
  const [ready, setReady] = useState(import.meta.env.VITE_FIXTURES !== "1");
  const { as, clock, latency } = params;
  useEffect(() => {
    if (import.meta.env.VITE_FIXTURES !== "1") return undefined;
    let cancelled = false;
    let restore: (() => void) | undefined;
    void import("../fixtures/install").then(({ installSeedFixtures }) => {
      if (cancelled) return;
      restore = installSeedFixtures({ persona: as, clock, latency });
      setReady(true);
    });
    return () => {
      cancelled = true;
      restore?.();
    };
  }, [as, clock, latency]);
  return ready;
}

export interface ScreenEntry {
  title: string;
  Component: ComponentType<{ params: FixtureParams }>;
}

// Catalogue ID (chapter 04 section 9.2) to the L4 screen that renders it in fixture mode.
// Screens register themselves as their epics land; nothing is registered yet.
const SCREENS = new Map<string, ScreenEntry>();

export function registerScreen(id: string, entry: ScreenEntry): void {
  SCREENS.set(id, entry);
}

export function unregisterScreen(id: string): void {
  SCREENS.delete(id);
}

export function screenById(id: string): ScreenEntry | undefined {
  return SCREENS.get(id);
}
