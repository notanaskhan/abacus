// TXP-12 · K-1 package A–F (T-02-T25): T-02-T08's personas and clocks (tax-returns.ts), each
// answering the K-1 reads for its artboard (seed/k1-packages.ts). Each artboard also names the
// return it opens and what it opens with (a row expanded, the K-3 tooltip, a dialog).
import {
  BLUESTEM_RETURN,
  CALLOWAY_RETURN,
  EMPTY_RETURN,
  RIDGELINE_RETURN,
} from "../seed/k1-packages";

export { txp12 as scenarios } from "./tax-returns";

export type Txp12State = "a" | "a2" | "a3" | "a4" | "a5" | "b" | "b2" | "c" | "d" | "e" | "f";

/** The return each artboard opens: Ridgeline, Bluestem (C), Calloway (D) or an empty 1065 (F). */
export const OPENS: Readonly<Record<Txp12State, string>> = {
  a: RIDGELINE_RETURN,
  a2: RIDGELINE_RETURN,
  a3: RIDGELINE_RETURN,
  a4: RIDGELINE_RETURN,
  a5: RIDGELINE_RETURN,
  b: RIDGELINE_RETURN,
  b2: RIDGELINE_RETURN,
  c: BLUESTEM_RETURN,
  d: CALLOWAY_RETURN,
  e: RIDGELINE_RETURN,
  f: EMPTY_RETURN,
};

/** What an interaction artboard opens on: a row, the K-3 tooltip, or a dialog. */
export interface Txp12Opening {
  expand?: string;
  tooltip?: boolean;
  dialog?: "share" | "release" | "resend";
  resendFor?: string;
}

export const OPENING: Readonly<Partial<Record<Txp12State, Txp12Opening>>> = {
  a2: { expand: "Jonah Feld" },
  a3: { tooltip: true },
  a4: { dialog: "share" },
  a5: { dialog: "release" },
  b2: { dialog: "resend", resendFor: "Pell Street II LLC" },
};
