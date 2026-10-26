// SHL-04 a–g (P-01 §5.3): one scenario per artboard, plus b′ (`bp`, nothing waiting) and the Raj
// Malhotra Approvals variant (`b_raj`). a–f stand at Mon Sep 14, 9:41 AM CT, g at Thu Oct 1,
// 11:00 AM CT. The data is fixtures/seed/notifications.ts (P-01-T07); the scenarios stay beside it
// under fixtures/scenarios/ and are re-exported here, with `settings` (the Notification settings
// menu, R2).
import { scenarios as all } from "../../fixtures/scenarios/SHL-04";

export const scenarios = {
  a: all.a,
  b: all.b,
  bp: all.bp,
  b_raj: all.b_raj,
  c: all.c,
  d: all.d,
  e: all.e,
  f: all.f,
  g: all.g,
  settings: all.settings,
};

export type Shl04State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Shl04State[];
