// The engagements domain's public entry (P-07 §5): what screens import.
export { GATE_NAMES, GateBlock, type GateBlockProps, gateLine } from "./GateBlock";
export {
  allows,
  bandRows,
  conflictOf,
  gateOf,
  useEngagementRecord,
  useEngagementWorkItems,
  useRecordLetter,
  waitsOnLetter,
} from "./record";
export { useDraft, useDraftWrites, useEngagementTypes } from "./wizard";
export {
  DEFAULT_ENGAGEMENT_FILTERS,
  ENGAGEMENT_LINES,
  ENGAGEMENT_TILES,
  type EngagementFilters,
  type EngagementLine,
  type EngagementPeriod,
  type NextDueWindow,
  isEngagementLine,
  isEngagementTile,
  isNarrowedIndex,
  useEngagementIndex,
} from "./list";
