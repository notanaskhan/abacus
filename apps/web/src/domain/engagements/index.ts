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
