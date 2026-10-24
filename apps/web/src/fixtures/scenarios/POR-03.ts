// POR-03 Documents (R-01-T05): one scenario per artboard, a–i, motion, c2 and M
// (docs/screens/POR-03.md). Each is a data condition on C5 section portal-pbc; what the client is
// doing at that instant (files over the list, the Ignore popover open, uploads in flight, the
// viewport) is the artboard's `ARTBOARD` entry, which the screen's tests and the gallery replay.
// Clocks: E0, Mon Sep 14, 2026, 9:24 AM CT, except c2 at 9:12 AM (the time of Claire's email).

import type { PortalBinderOut } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { portalDocumentsHandlers } from "../handlers/portal-documents";
import { DEMO_INSTANT } from "../seed/clock";
import {
  FELD,
  FELD_2024,
  FELD_2025,
  FELD_DROP,
  FELD_DROP_FILES,
  FELD_ROWS_A,
  FELD_ROWS_C,
  FELD_ROWS_C2,
  FELD_ROWS_G,
  FELD_UPLOADS_IN_FLIGHT,
  THREADS,
  danaBinder,
  feldBinder,
  feldClosed2024,
  feldCaughtUp,
  sheet1095c,
} from "../seed/portal-documents";

/** Mon Sep 14, 2026, 9:12 AM CT: Claire's email with the 1095-C (POR-03 c2). */
export const EMAIL_CLOCK = "2026-09-14T09:12:00-05:00";

/** What the client is doing at the artboard's instant. */
export interface Por03Artboard {
  binderId: string;
  /** Files dragged over the list (b) or flying in (motion). */
  dragging?: readonly string[];
  /** The drop motion plays (frozen at the sorted frame under `?static=1` or reduced motion). */
  motion?: boolean;
  /** The drop batch the screen polls after the drop (c, d). */
  dropBatch?: string;
  /** The request whose Ignore popover is open (f). */
  ignoreOpenOn?: string;
  /** Files uploading from this browser, shown in the rail's Uploading band (a, M). */
  uploads?: readonly { name: string; sizeBytes: number; percent: number }[];
  /** The 390 layout. */
  mobile?: boolean;
}

const at = (
  state: string,
  persona: string,
  binder: PortalBinderOut,
  clock = DEMO_INSTANT,
  extra: { drop?: boolean } = {},
): Scenario => ({
  state,
  persona,
  clock,
  handlers: {
    ...portalHandlers({ clock }),
    ...portalDocumentsHandlers({
      clock,
      binders: persona === "claire-feld" ? [FELD_2025, FELD_2024] : [binder.binder],
      binder,
      ...(persona === "claire-feld" ? { others: [feldClosed2024()] } : {}),
      requests: persona === "claire-feld" ? [sheet1095c()] : [],
      threads: THREADS,
      ...(extra.drop === true ? { drop: FELD_DROP } : {}),
    }),
  },
});

const A = feldBinder(FELD_ROWS_A);
const C = feldBinder(FELD_ROWS_C);

export const scenarios = defineScenarios({
  a: at("a", "claire-feld", A),
  motion: at("motion", "claire-feld", C, DEMO_INSTANT, { drop: true }),
  b: at("b", "claire-feld", A),
  c: at("c", "claire-feld", C, DEMO_INSTANT, { drop: true }),
  c2: at("c2", "claire-feld", feldBinder(FELD_ROWS_C2), EMAIL_CLOCK),
  d: at("d", "claire-feld", C, DEMO_INSTANT, { drop: true }),
  e: at("e", "claire-feld", feldBinder(FELD_ROWS_C2, { marked: true })),
  f: at("f", "claire-feld", A),
  g: at("g", "claire-feld", feldBinder(FELD_ROWS_G)),
  h: at("h", "claire-feld", feldCaughtUp()),
  i: at("i", "dana-kowalski", danaBinder()),
  M: at("M", "claire-feld", A),
});

export type Por03State = keyof typeof scenarios;

const DANA = danaBinder().binder.id;

export const ARTBOARD: Readonly<Record<Por03State, Por03Artboard>> = {
  a: { binderId: FELD.binder, uploads: FELD_UPLOADS_IN_FLIGHT },
  motion: {
    binderId: FELD.binder,
    dragging: FELD_DROP_FILES,
    motion: true,
    dropBatch: FELD.dropBatch,
  },
  b: { binderId: FELD.binder, dragging: FELD_DROP_FILES },
  c: { binderId: FELD.binder, dropBatch: FELD.dropBatch },
  c2: { binderId: FELD.binder },
  d: { binderId: FELD.binder, dropBatch: FELD.dropBatch },
  e: { binderId: FELD.binder },
  f: { binderId: FELD.binder, ignoreOpenOn: FELD.form1095c },
  g: { binderId: FELD.binder },
  h: { binderId: FELD.binder },
  i: { binderId: DANA },
  M: { binderId: FELD.binder, uploads: FELD_UPLOADS_IN_FLIGHT, mobile: true },
};
