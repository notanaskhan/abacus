// Shared product copy (F-05-T32; plan 04 §8.1): the verbs and states every screen repeats, in a
// firm namespace and a portal-safe one. The portal never says the product's name (DEC-01,
// ADR-133), so it has its own error body and no agent words. The strings are the C-20 States kit's
// and the C-22 Modal kit's (`STATE_COPY` in packages/ui), never rewritten here.
import { STATE_COPY } from "@abacus/ui";
import { defineCopy } from "./registry";

const shared = {
  retry: STATE_COPY.retry,
  clearFilters: STATE_COPY.clearFilters,
  loading: STATE_COPY.loading,
  offline: STATE_COPY.offline,
  /** "Couldn’t load sessions." The noun is the pane's own, lower case. */
  couldntLoad: (noun: string) => `Couldn’t load ${noun}.`,
  cancel: "Cancel",
  discardTitle: "Discard changes?",
  discard: "Discard",
} as const;

export const COMMON_FIRM = defineCopy("common.firm", {
  ...shared,
  errorBody: STATE_COPY.errorBody,
  running: STATE_COPY.running,
  queued: STATE_COPY.queued,
  agentRunning: STATE_COPY.agentRunning,
  viewRun: STATE_COPY.viewRun,
});

export const COMMON_PORTAL = defineCopy("common.portal", {
  ...shared,
  errorBody: STATE_COPY.errorBodyPortal,
});

/** The shared words for a surface: the portal entry takes only the portal-safe namespace. */
export function commonCopy(surface: "firm" | "portal"): typeof COMMON_FIRM | typeof COMMON_PORTAL {
  return surface === "portal" ? COMMON_PORTAL : COMMON_FIRM;
}
