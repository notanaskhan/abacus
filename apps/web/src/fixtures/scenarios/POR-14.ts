// POR-14 Third-party request room (R-01-T05): one scenario per artboard, a–f
// (docs/screens/POR-14.md), each a data condition on `GET /v1/portal/room`. a, b, c and e are Sam
// Ortiz (Keystone Retirement Services) at their own dates; d is Harborline Trust Company's
// certifications contact; f is an expired, used or unknown invitation (no room: every read 404).

import type { PortalRoomOut } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { portalDocumentsHandlers } from "../handlers/portal-documents";
import { DEMO_INSTANT } from "../seed/clock";
import {
  BRIDGE_ID,
  HARBORLINE_D,
  KEYSTONE_A,
  KEYSTONE_B,
  KEYSTONE_C,
  KEYSTONE_E,
  ROOM_THREADS,
} from "../seed/portal-documents";

/** The artboards' own days (POR-14 README): b Tue Sep 22, c Wed Sep 23, d Fri Sep 11, e Mon Sep 28,
 * each at 9:24 AM CT like the epoch. */
export const ROOM_CLOCKS = {
  b: "2026-09-22T09:24:00-05:00",
  c: "2026-09-23T09:24:00-05:00",
  d: "2026-09-11T09:24:00-05:00",
  e: "2026-09-28T09:24:00-05:00",
} as const;

export interface Por14Artboard {
  /** The row open on arrival (a: the bridge letter). */
  expanded?: string;
}

const roomAt = (
  state: string,
  persona: string,
  room: PortalRoomOut | undefined,
  clock: string = DEMO_INSTANT,
): Scenario => ({
  state,
  persona,
  clock,
  handlers: {
    ...portalHandlers({ clock }),
    ...portalDocumentsHandlers({
      clock,
      threads: ROOM_THREADS,
      ...(room === undefined ? {} : { room }),
    }),
  },
});

const BUILD = {
  a: () => roomAt("a", "sam-ortiz", KEYSTONE_A),
  b: () => roomAt("b", "sam-ortiz", KEYSTONE_B, ROOM_CLOCKS.b),
  c: () => roomAt("c", "sam-ortiz", KEYSTONE_C, ROOM_CLOCKS.c),
  d: () => roomAt("d", "harborline-certifications", HARBORLINE_D, ROOM_CLOCKS.d),
  e: () => roomAt("e", "sam-ortiz", KEYSTONE_E, ROOM_CLOCKS.e),
  f: () => roomAt("f", "sam-ortiz", undefined),
} as const;

export type Por14State = keyof typeof BUILD;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  d: BUILD.d(),
  e: BUILD.e(),
  f: BUILD.f(),
});

/** A scenario with handlers of its own: the writes it answers (an upload, a comment, a
 * withdrawal) change only its own room (tests that write start from the artboard each time). */
export function freshScenario(state: Por14State): Scenario {
  return BUILD[state]();
}

export const ARTBOARD: Readonly<Record<Por14State, Por14Artboard>> = {
  a: { expanded: BRIDGE_ID },
  b: { expanded: BRIDGE_ID },
  c: { expanded: BRIDGE_ID },
  d: {},
  e: {},
  f: {},
};
