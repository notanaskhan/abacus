// AUD-06 a–h and the five added states (A-02-T05): one scenario per artboard. The data and handlers
// live under fixtures/scenarios/AUD-06.ts; OPENS names the engagement, TB, tab, layer and overlay
// each artboard opens on. A-02-T09 (a, c) and A-02-T14 (b, d, e, g, h) draw the screen on them.
import { OPENS, scenarios } from "../../fixtures/scenarios/AUD-06";

export { OPENS, scenarios };

export type Aud06State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Aud06State[];

/** The artboards the handoff draws; the rest are added states (A-02 §2.1). */
export const ARTBOARDS: readonly Aud06State[] = ["a", "b", "c", "d", "e", "f", "g", "h"];
