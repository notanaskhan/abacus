// POR-23 Component auditor room, Harlow & Pike Distribution, Inc. (A-09-T36): one scenario per
// artboard a-f of the handoff, all Renee Pruett's (Pruett & Lang LLP, the component auditor): a
// invited (Wed Sep 23, 9:40 AM), b acknowledged with a question (11:20 AM), c deliverable overdue
// (Tue Dec 1, 9:05 AM), d uploaded (Wed Dec 2), e returned, f the invitation expired.
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { componentRoomHandlers } from "../handlers/component-room";
import { portalHandlers } from "../handlers/portal";
import type { Por23State } from "../seed/group-audit";

export const POR23_CLOCKS: Readonly<Record<Por23State, string>> = {
  a: "2026-09-23T09:40:00-05:00",
  b: "2026-09-23T11:20:00-05:00",
  c: "2026-12-01T09:05:00-06:00",
  d: "2026-12-02T10:00:00-06:00",
  e: "2026-12-02T10:00:00-06:00",
  f: "2026-09-23T09:40:00-05:00",
};

const at = (state: Por23State): Scenario => ({
  state,
  persona: "renee-pruett",
  clock: POR23_CLOCKS[state],
  handlers: { ...portalHandlers({ clock: POR23_CLOCKS[state] }), ...componentRoomHandlers(state) },
});

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e"),
  f: at("f"),
});

export type Por23Scenario = keyof typeof scenarios;
